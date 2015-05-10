# coding: utf-8

from fabkit import sudo, env, user, filer
from fablib import python
import openstack_util
from fablib.base import SimpleBase

MODE_CONTROLLER = 1
MODE_COMPUTE = 2


class Neutron(SimpleBase):
    def __init__(self, mode=MODE_CONTROLLER):
        self.mode = mode
        self.data_key = 'neutron'
        self.data = {
            'user': 'neutron',
            'auth_strategy': 'keystone',
            'rpc_backend': 'neutron.openstack.common.rpc.impl_kombu',
            'core_plugin': 'ml2',
        }

        if mode == MODE_CONTROLLER:
            self.services = ['openstack-neutron-server']
        elif mode == MODE_COMPUTE:
            self.services = ['openstack-neutron-linuxbridge-agent']

    def init_data(self):
        self.connection = openstack_util.get_mysql_connection(self.data)
        self.data.update({
            'keystone': env.cluster['keystone'],
            'database': {
                'connection': self.connection['str'],
            },
        })

    def setup(self):
        data = self.get_init_data()

        openstack_util.setup_common()

        user.add(data['user'])

        sudo('pip install python-neutronclient')

        pkg = python.install_from_git(
            'neutron',
            'https://github.com/openstack/neutron.git -b stable/icehouse')

        if not filer.exists('/etc/neutron'):
            sudo('cp -r {0}/etc/ /etc/neutron/'.format(pkg['git_dir']))

        if not filer.exists('/etc/neutron/plugins'):
            sudo('cp -r {0}/etc/neutron/plugins/ /etc/neutron/plugins/'.format(pkg['git_dir']))

        nova_tenant_id = openstack_util.client_cmd(
            'keystone tenant-list | awk \'/ service / { print $2 }\'')
        nova_tenant_id = nova_tenant_id.split('\r\n')[-1]
        data['nova_admin_tenant_id'] = nova_tenant_id

        is_updated = filer.template(
            '/etc/neutron/neutron.conf',
            data=data,
        )

        is_updated = filer.template(
            '/etc/neutron/plugins/ml2/ml2_conf.ini',
            data=data,
        ) or is_updated

        is_updated = filer.template(
            '/etc/neutron/plugins/linuxbridge/linuxbridge_conf.ini',
            data=data,
        ) or is_updated

        filer.mkdir('/var/log/neutron', owner='neutron:neutron')

        # 他のコンポーネントはconfファイルを指定しなくても所定の位置を読んでくれているが、
        # neutronは、プラグインの含めてconfファイルを指定しないと読んでくれない
        option = '--log-dir /var/log/neutron/ --config-file /etc/neutron/neutron.conf' \
            + ' --config-file /etc/neutron/plugins/ml2/ml2_conf.ini' \
            + ' --config-file /etc/neutron/plugins/linuxbridge/linuxbridge_conf.ini'
        is_updated = filer.template('/etc/init.d/openstack-neutron-server', '755',
                                    data={
                                        'prog': 'neutron-server',
                                        'option': option,
                                        'config': '/etc/neutron/neutron.conf',
                                        'user': data['user'],
                                    },
                                    src_target='initscript') or is_updated

        is_updated = filer.template('/etc/init.d/openstack-neutron-linuxbridge-agent', '755',
                                    data={
                                        'prog': 'neutron-linuxbridge-agent',
                                        'option': option,
                                        'config': '/etc/neutron/neutron.conf',
                                        'user': data['user'],
                                    },
                                    src_target='initscript')

        # neutronはdb_syncなどは行わない
        # サービスの初回立ち上げ時に、プラグインを読み込んで、そのプラグインにそったテーブルを作成する
        self.enable_services().start_services(pty=False)

        if is_updated:
            self.restart_services(pty=False)

        return 0

    def cmd(self, cmd):
        return openstack_util.client_cmd('neutron {0}'.format(cmd))
