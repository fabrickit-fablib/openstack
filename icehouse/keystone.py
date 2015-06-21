# coding:utf-8

import time
from fabkit import sudo, api, filer, user, run
from fablib import python
from fablib.base import SimpleBase
import openstack_util


class Keystone(SimpleBase):
    def __init__(self, data=None):
        self.data_key = 'keystone'
        self.data = {
            'user': 'keystone',
            'admin_token': 'ADMIN',
            'token': {
                'provider': 'keystone.token.providers.uuid.Provider'
            },
        }

        self.services = {
            'CentOS [67].*': ['openstack-keystone']
        }

    def init_data(self):
        self.connection = openstack_util.get_mysql_connection(self.data)
        self.data.update({
            'tmp_admin_token': 'admin_token = {0}'.format(self.data['admin_token']),
            'database': {
                'connection': self.connection['str']
            },
        })

    def setup(self):
        data = self.get_init_data()

        user.add(data['user'])
        openstack_util.setup_common()

        # keystoneのrequirements.txtには、lxml>=2.3,<=3.4.2 となっているが、
        # 3.4系はインストールに失敗するため、先に3.4以前のバージョンをインストールしておく
        sudo('pip install "lxml>=2.3,<3.4"')

        keystone = python.install_from_git(
            'keystone', 'https://github.com/openstack/keystone.git -b stable/icehouse')

        if not filer.exists('/etc/keystone'):
            sudo('cp -r {0}/etc/ /etc/keystone/'.format(keystone['git_dir']))

        is_updated = filer.template(
            '/etc/keystone/keystone.conf',
            data=data,
        )

        filer.mkdir('/var/log/keystone', owner='keystone:keystone')
        option = ' --log-dir /var/log/keystone'
        is_updated = filer.template('/etc/init.d/openstack-keystone', '755',
                                    data={
                                        'prog': 'keystone-all',
                                        'option': option,
                                        'config': '/etc/keystone/keystone.conf',
                                        'user': self.data['user'],
                                    },
                                    src_target='initscript') or is_updated

        self.db_sync()

        self.enable_services().start_services(pty=False)
        if is_updated:
            self.restart_services(pty=False)

        time.sleep(3)  # 立ち上げてすぐにはLISTENしないので、3秒待つ

        self.create_tenant('admin', 'Admin Tenant')
        self.create_role('admin')
        self.create_role('_member_')
        self.create_user(data['admin_user'], data['admin_password'],
                         [['admin', 'admin'], ['admin', '_member_']])

        self.create_tenant(data['service_tenant_name'], 'Service Tenant')
        self.create_user(data['service_user'], data['service_password'], [['service', 'admin']])

        for name, service in data['services'].items():
            self.create_service(name, service)

        self.disable_admin_token()

    def disable_admin_token(self):
        data = self.get_init_data()
        data.update({
            'tmp_admin_token': '# admin_token ='
        })
        filer.template(
            '/etc/keystone/keystone.conf',
            data=data,
        )
        self.restart_services(pty=False)

    def db_sync(self):
        # db_sync
        if not openstack_util.show_tables(self.connection) == sorted([
            'assignment', 'credential', 'domain', 'endpoint', 'group', 'migrate_version',
            'policy', 'project', 'region', 'role', 'service', 'token',
            'trust', 'trust_role', 'user', 'user_group_membership'
        ]):
            sudo('keystone-manage db_sync')

    def cmd(self, cmd):
        # create users, roles, services
        with api.shell_env(
                OS_SERVICE_TOKEN=self.data['admin_token'],
                OS_SERVICE_ENDPOINT='http://localhost:35357/v2.0',
                ):
            return run('keystone {0}'.format(cmd))

    def create_tenant(self, name, description):
        tenant_list = self.cmd('tenant-list')
        if ' {0} '.format(name) not in tenant_list:
            self.cmd('tenant-create --name={0} --description="{1}"'.format(
                name, description))

    def create_role(self, name):
        role_list = self.cmd('role-list')
        if ' {0} '.format(name) not in role_list:
            self.cmd('role-create --name={0}'.format(name))

    def create_user(self, name, password, tenant_roles):
        user_list = self.cmd('user-list')
        if ' {0} '.format(name) not in user_list:
            self.cmd('user-create --name={0} --pass={1}'.format(name, password))
            for tenant_role in tenant_roles:
                self.cmd('user-role-add --user={0} --tenant={1} --role={2}'.format(
                    name, tenant_role[0], tenant_role[1]))

    def create_service(self, name, service):
        service_list = self.cmd('service-list')
        endpoint_list = self.cmd('endpoint-list')
        if ' {0} '.format(name) not in service_list:
            self.cmd('service-create --name={0} --type={1[type]} --description="{1[description]}"'.format(name, service))  # noqa

        service_id = self.cmd('service-list | awk \'/ {0} / {{print $2}}\''.format(name))
        service_id = service_id.split('\r\n')[-1]
        if service_id not in endpoint_list:
            self.cmd('''endpoint-create \\
            --service-id={0} \\
            --publicurl={1[publicurl]} \\
            --internalurl={1[internalurl]} \\
            --adminurl={1[adminurl]}'''.format(service_id, service))

    def dump_openstackrc(self):
        data = self.get_init_data()
        openstack_util.dump_openstackrc(data)
