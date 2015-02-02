# coding: utf-8

from fabkit import sudo, env, Service, user, filer
from fablib import python
import openstack_util


class Neutron():
    data = {
        'user': 'neutron',
        'auth_strategy': 'keystone',
        'rpc_backend': 'neutron.openstack.common.rpc.impl_kombu',
        'core_plugin': 'ml2',
    }

    def __init__(self, data=None):
        if data:
            self.data.update(data)
        else:
            self.data.update(env.cluster['neutron'])

        self.keystone_data = env.cluster['keystone']
        self.data.update({
            'keystone_authtoken': self.keystone_data,
            'database': {
                'data': self.data['database'],
                'connection': openstack_util.convert_mysql_connection(self.data['database'])
            },
        })

        # controller
        self.neutron_server = Service('openstack-neutron-server')

        # compute
        self.neutron_linuxbridge_agent = Service('openstack-neutron-linuxbridge-agent')

    def setup(self):
        is_updated = self.install()

        self.neutron_server.enable().start(pty=False)

        if is_updated:
            self.neutron_server.restart(pty=False)

        return 0

    def setup_compute(self):
        is_updated = self.install_compute()
        self.neutron_linuxbridge_agent.enable().start()
        if is_updated:
            self.neutron_linuxbridge_agent.restart()
        return 0

    def cmd(self, cmd):
        return openstack_util.client_cmd('neutron {0}'.format(cmd), self.keystone_data)

    def install(self):
        openstack_util.setup_init()

        user.add(self.data['user'])

        sudo('pip install python-neutronclient')

        pkg = python.install_from_git(
            'neutron',
            'https://github.com/openstack/neutron.git -b stable/icehouse')

        if not filer.exists('/etc/neutron'):
            sudo('cp -r {0}/etc/ /etc/neutron/'.format(pkg['git_dir']))

        if not filer.exists('/etc/neutron/plugins'):
            sudo('cp -r {0}/etc/neutron/plugins/ /etc/neutron/plugins/'.format(pkg['git_dir']))

        nova_tenant_id = openstack_util.client_cmd(
            'keystone tenant-list | awk \'/ service / { print $2 }\'',
            self.keystone_data)
        nova_tenant_id = nova_tenant_id.split('\r\n')[-1]
        self.data['nova_admin_tenant_id'] = nova_tenant_id

        is_updated = filer.template(
            '/etc/neutron/neutron.conf',
            data=self.data,
        )

        is_updated = filer.template(
            '/etc/neutron/plugins/ml2/ml2_conf.ini',
            data=self.data,
        ) or is_updated

        filer.mkdir('/var/log/neutron', owner='neutron:neutron')
        option = '--log-dir /var/log/neutron/'
        is_updated = filer.template('/etc/init.d/openstack-neutron-server', '755',
                                    data={
                                        'prog': 'neutron-server',
                                        'option': option,
                                        'config': '/etc/neutron/neutron.conf',
                                        'user': self.data['user'],
                                    },
                                    src_target='initscript') or is_updated

        return is_updated

    def install_compute(self):
        filer.mkdir('/var/log/neutron', owner='neutron:neutron')
        option = '--config-file /etc/neutron/neutron.conf --config-file /etc/neutron/plugins/ml2/ml2_conf.ini --log-file /var/log/neuton/neutron-linuxbridge-agent'  # noqa
        is_updated = filer.template('/etc/init.d/openstack-neutron-linuxbridge-agent', '755',
                                    data={
                                        'prog': 'neutron-linuxbridge-agent',
                                        'option': option,
                                        'config': '/etc/neutron/neutron.conf',
                                        'user': self.data['user'],
                                    },
                                    src_target='initscript')

        return is_updated
