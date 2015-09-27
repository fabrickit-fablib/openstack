# coding: utf-8

from fabkit import sudo, env, Package, filer
from fablib.python import Python
from tools import Tools
from fablib.base import SimpleBase

MODE_CONTROLLER = 'controller'
MODE_COMPUTE = 'compute'


class Nova(SimpleBase):
    def __init__(self, mode=MODE_CONTROLLER):
        self.data_key = 'nova'
        self.mode = mode
        self.data = {
            'debug': 'true',
            'verbose': 'true',
            'timeout_nbd': 1,
        }

        if mode == MODE_CONTROLLER:
            self.services = [
                'nova-api',
                'nova-cert',
                'nova-console',
                'nova-consoleauth',
                'nova-scheduler',
                'nova-conductor',
                'nova-novncproxy',
            ]

        elif mode == MODE_COMPUTE:
            self.services = [
                'libvirtd',
                'messagebus',
                'nova-compute',
            ]

    def init_before(self):
        self.package = env['cluster']['os_package_map']['nova']
        self.prefix = self.package.get('prefix', '/usr')
        self.python = Python(self.prefix)
        self.tools = Tools(self.python)

    def init_after(self):
        self.data.update({
            'user': 'nova',
            'timeout_nbd': 1,
            'sudoers_cmd': '/usr/bin/nova-rootwrap /etc/nova/rootwrap.conf *',
            'lock_path': '/var/lock/subsys/nova',
            'my_ip': env.node['ip']['default_dev']['ip'],
            'vncserver_listen': env.node['ip']['default_dev']['ip'],
            'vncserver_proxyclient_address': env.node['ip']['default_dev']['ip'],
            'keystone': env.cluster['keystone'],
        })

    def setup(self):
        data = self.init()
        is_updated = False

        if self.is_tag('package'):
            self.tools.setup()
            if self.mode == MODE_CONTROLLER:
                Package('novnc').install()

            if self.mode == MODE_COMPUTE:
                Package('libvirt').install()
                Package('sysfsutils').install()
                Package('qemu-kvm').install()
                Package('libvirt-python').install()
                Package('libvirt-devel').install()
                Package('dbus').install()

                # libvirt-pythonを利用するには、ディストリビューションのものをコピーする必要がある
                # http://d.hatena.ne.jp/pyde/20130831/p1
                # site_packages = self.python.get_site_packages()
                # libvirt_python = run('rpm -ql libvirt-python | grep site-packages').split('\r\n')
                # for src in libvirt_python:
                #     sudo('ln -s {0} {1}'.format(src, site_packages))

            self.python.install_from_git(**self.package)

            if not filer.exists('/usr/bin/nova'):
                sudo('ln -s {0}/bin/nova /usr/bin/'.format(self.prefix))
            if not filer.exists('/usr/bin/nova-manage'):
                sudo('ln -s {0}/bin/nova-manage /usr/bin/'.format(self.prefix))
            if not filer.exists('/usr/bin/nova-rootwrap'):
                sudo('ln -s {0}/bin/nova-rootwrap /usr/bin/'.format(self.prefix))

        if self.is_tag('conf'):
            # sudoersファイルは最後に改行入れないと、シンタックスエラーとなりsudo実行できなくなる
            # sudo: >>> /etc/sudoers.d/nova: syntax error near line 2 <<<
            # この場合は以下のコマンドでvisudoを実行し、編集する
            # $ pkexec visudo -f /etc/sudoers.d/nova
            is_updated = filer.template(
                '/etc/sudoers.d/nova',
                data=data,
                src='sudoers.j2',
            )

            is_updated = filer.template(
                '/etc/nova/nova.conf',
                src='{0}/nova.conf.j2'.format(data['version']),
                data=data,
            ) or is_updated

        if self.is_tag('data'):
            if self.mode == MODE_CONTROLLER:
                sudo('nova-manage db sync')

        if self.is_tag('service'):
            self.enable_services().start_services(pty=False)
            if is_updated:
                self.restart_services(pty=False)

        if self.is_tag('data'):
            if self.mode == MODE_CONTROLLER:
                self.sync_flavors()

        return 0

    def cmd(self, cmd):
        self.init()
        return self.tools.cmd('nova {0}'.format(cmd))

    def check(self):
        self.nova_api.status()
        self.nova_cert.status()
        self.nova_consoleauth.status()
        self.nova_scheduler.status()
        self.nova_conductor.status()
        self.nova_novncproxy.status()

    def enable_nova_services(self):
        result = sudo("nova-manage service list 2>/dev/null | grep disabled | awk '{print $1,$2}'")
        services = result.split('\r\n')
        services = map(lambda s: s.split(' '), services)
        for service in services:
            sudo("nova-manage service enable --service {0} --host {1}".format(
                service[0], service[1]))

    def sync_flavors(self):
        data = self.init()

        result = self.cmd("flavor-list 2>/dev/null | grep '| ' | grep -v '| ID' | awk '{print $4}'")
        flavor_list = result.split('\r\n')
        sub_set = set(flavor_list) - set(data['flavors'].keys())
        for flavor_name in sub_set:
            if len(flavor_name) == 0:
                continue
            self.cmd("flavor-delete {0}".format(flavor_name))

        for flavor_name, flavor in data['flavors'].items():
            if flavor_name not in flavor_list:
                flavor = map(lambda f: str(f), flavor)
                options = ' '.join(flavor)
                self.cmd("flavor-create --is-public true {0} auto {1}".format(flavor_name, options))
