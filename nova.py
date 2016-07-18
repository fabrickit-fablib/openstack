# coding: utf-8

from fabkit import sudo, env, filer, api
from fablib.python import Python
from fablib.base import SimpleBase
import re
import utils


class Nova(SimpleBase):
    def __init__(self, enable_services=['.*']):
        self.data_key = 'nova'
        self.data = {
            'debug': 'true',
            'verbose': 'true',
            'timeout_nbd': 1,
            'is_nova-api': False,
            'is_master': False,
        }

        default_services = [
            'nova-api',
            'nova-scheduler',
            'nova-conductor',
            'nova-consoleauth',
            'nova-novncproxy',
            'nova-compute',
        ]

        self.packages = []
        self.services = []
        for service in default_services:
            for enable_service in enable_services:
                if re.search(enable_service, service):
                    self.services.append(service)
                    break

        if 'nova-api' in self.services:
            self.data['is_nova-api'] = True

        if 'nova-novncproxy' in self.services:
            self.packages.append('novnc')

        if 'nova-compute' in self.services:
            self.services.extend([
                'libvirtd',
                'messagebus',
                'nova-compute',
            ])

            self.packages.extend([
                'libvirt',
                'sysfsutils',
                'qemu-kvm',
                'libvirt-python',
                'libvirt-devel',
                'dbus',
            ])

    def init_before(self):
        self.package = env['cluster']['os_package_map']['nova']
        self.prefix = self.package.get('prefix', '/usr')
        self.python = Python(self.prefix)

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

        if env.host == env.hosts[0] and self.data['is_nova-api']:
            self.data['is_master'] = True
        else:
            self.data['is_master'] = False

    def setup(self):
        data = self.init()

        if self.is_tag('package'):
            self.install_packages()
            self.python.setup()
            self.python.setup_package(**self.package)

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
            if filer.template(
                '/etc/sudoers.d/nova',
                data=data,
                src='sudoers.j2',
                    ):
                self.handlers['restart_nova'] = True

            if filer.template(
                '/etc/nova/nova.conf',
                src='{0}/nova.conf.j2'.format(data['version']),
                data=data,
                    ):
                self.handlers['restart_nova'] = True

        if self.is_tag('data') and env.host == env.hosts[0]:
            if data['is_master']:
                sudo('nova-manage db sync')

                if data['version'] in ['mitaka']:
                    sudo('nova-manage api_db sync')

        if self.is_tag('service'):
            self.enable_services().start_services(pty=False)
            self.exec_handlers()

        if self.is_tag('data') and env.host == env.hosts[0]:
            if data['is_master']:
                self.sync_flavors()

        return 0

    def cmd(self, cmd):
        self.init()
        return utils.oscmd('nova {0}'.format(cmd))

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

    def create_flavor(self, name, ram, disk, vcpu):
        with api.warn_only():
            result = self.cmd("flavor-list 2>/dev/null | grep ' {0} '".format(name))

        if result.return_code == 0:
            return

        else:
            self.cmd("flavor-create --is-public true {0} auto {1} {2} {3}".format(
                name, ram, disk, vcpu))
