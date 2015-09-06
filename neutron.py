# coding: utf-8

from fabkit import sudo, env, user, filer, run
from fablib.python import Python
import openstack_util
from fablib.base import SimpleBase

MODE_CONTROLLER = 1
MODE_COMPUTE = 2


class Neutron(SimpleBase):
    def __init__(self, mode=MODE_CONTROLLER):
        self.prefix = '/opt/neutron'
        self.python = Python(self.prefix, '2.7')
        self.mode = mode
        self.data_key = 'neutron'
        self.data = {
            'sudoers_cmd': 'ALL',
            'debug': True,
            'verbose': True,
            'user': 'neutron',
            'auth_strategy': 'keystone',
            'rpc_backend': 'neutron.openstack.common.rpc.impl_kombu',
            'core_plugin': 'ml2',
        }

        if mode == MODE_CONTROLLER:
            self.services = ['os-neutron-server']
        elif mode == MODE_COMPUTE:
            self.services = ['os-neutron-linuxbridge-agent']

    def init_data(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
        })

    def setup(self):
        data = self.init()

        if self.is_package:
            openstack_util.setup_common(self.python)
            user.add(data['user'])

            self.python.install('python-neutronclient')
            if not filer.exists('/usr/bin/neutron'):
                sudo('ln -s {0}/bin/neutron /usr/bin/'.format(self.prefix))

            pkg = self.python.install_from_git(
                'neutron',
                'https://github.com/openstack/neutron.git -b {0}'.format(data['branch']),
                git_dir='/opt/ossrc/neutron',
                is_develop=False)

            if not filer.exists('/etc/neutron'):
                sudo('cp -r {0}/etc/ /etc/neutron/'.format(pkg['git_dir']))
            if not filer.exists('/etc/neutron/plugins'):
                sudo('cp -r {0}/etc/neutron/plugins/ /etc/neutron/plugins/'.format(pkg['git_dir']))

            filer.mkdir('/var/log/neutron', owner='neutron:neutron')

        if self.is_conf:
            is_updated = filer.template(
                '/etc/sudoers.d/neutron',
                data=data,
                src='sudoers.j2',
            )

            # nova_tenant_id = 'fe45c11a774049efb6dc08f32e43a837'

            # openstack_util.client_cmd(
            #     'project list | awk \'/ service / { print $2 }\'')
            # nova_tenant_id = nova_tenant_id.split('\r\n')[-1]
            # data['nova_admin_tenant_id'] = nova_tenant_id
            nova_tenant_id = openstack_util.client_cmd(
                'keystone tenant-list 2> /dev/null | awk \'/ service / { print $2 }\'')
            data['nova_admin_tenant_id'] = nova_tenant_id

            is_updated = filer.template(
                '/etc/neutron/neutron.conf',
                src='{0}/neutron.conf.j2'.format(data['version']),
                data=data,
            )

            is_updated = filer.template(
                '/etc/neutron/plugins/ml2/ml2_conf.ini',
                src='{0}/ml2_conf.ini.j2'.format(data['version']),
                data=data,
            ) or is_updated

            is_updated = filer.template(
                '/etc/neutron/plugins/linuxbridge/linuxbridge_conf.ini',
                src='{0}/linuxbridge_conf.ini.j2'.format(data['version']),
                data=data,
            ) or is_updated

            # 他のコンポーネントはconfファイルを指定しなくても所定の位置を読んでくれているが、
            # neutronは、プラグインの含めてconfファイルを指定しないと読んでくれない
            option = '--config-file /etc/neutron/neutron.conf' \
                + ' --config-file /etc/neutron/plugins/ml2/ml2_conf.ini' \
                + ' --config-file /etc/neutron/plugins/linuxbridge/linuxbridge_conf.ini'

            # create tables
            # juno以前は、neutron-serverの起動時にtable作成が行われてたが、juno以降では以下のコマンドでtableを作る
            run('{0}/bin/neutron-db-manage {1} upgrade head'.format(self.prefix, option))

            option = '--log-dir /var/log/neutron/ {0}'.format(option)

            is_updated = filer.template('/etc/systemd/system/os-neutron-server.service',
                                        '755', data={
                                            'prefix': self.prefix,
                                            'prog': 'neutron-server',
                                            'option': option,
                                            'user': self.data['user'],
                                        },
                                        src='systemd.service')

            is_updated = filer.template('/etc/systemd/system/os-neutron-linuxbridge-agent.service',
                                        '755', data={
                                            'prefix': self.prefix,
                                            'prog': 'neutron-linuxbridge-agent',
                                            'option': option,
                                            'user': self.data['user'],
                                        },
                                        src='systemd.service')

            # is_updated = filer.template('/etc/init.d/os-neutron-linuxbridge-agent',
            #                             '755', data={
            #                                 'prefix': self.prefix,
            #                                 'prog': 'neutron-linuxbridge-agent',
            #                                 'option': option,
            #                                 'user': self.data['user'],
            #                             },
            #                             src_target='initd.sh')

            # neutronはdb_syncなどは行わない
            # サービスの初回立ち上げ時に、プラグインを読み込んで、そのプラグインにそったテーブルを作成する
            self.enable_services().start_services(pty=False)

            if is_updated:
                self.restart_services(pty=False)

        if self.is_data:
            self.create_nets()

        return 0

    def cmd(self, cmd):
        return openstack_util.client_cmd('neutron {0}'.format(cmd))

    def create_nets(self):
        data = self.init()

        result = self.cmd("net-list 2>/dev/null | grep '| ' | grep -v '| id' | awk '{print $4}'")
        net_list = result.split('\r\n')
        result = self.cmd("subnet-list 2>/dev/null | grep '| ' | grep -v '| id' | awk '{print $4}'")
        subnet_list = result.split('\r\n')

        for network_name, network in data['networks'].items():
            if network_name not in net_list:
                tmp_options = map(lambda opt: '--' + opt, network['options'])
                options = ' '.join(tmp_options)
                self.cmd('net-create {0} {1}'.format(options, network_name))

            for subnet_name, subnet in network['subnets'].items():
                if subnet_name not in subnet_list:
                    tmp_options = map(lambda opt: '--' + opt, subnet['options'])
                    options = ' '.join(tmp_options)
                    self.cmd('subnet-create {0} {1} --name {2} {3}'.format(
                        network_name, subnet['cidr'], subnet_name, options))
