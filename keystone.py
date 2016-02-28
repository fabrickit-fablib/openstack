# coding:utf-8

import time
from fabkit import sudo, api, filer, run, env
from fablib.python import Python
from fablib.base import SimpleBase


class Keystone(SimpleBase):
    def __init__(self, data=None):
        self.data_key = 'keystone'
        self.data = {
            'user': 'keystone',
            'admin_token': 'ADMIN',
            'token': {
                'provider': 'keystone.token.providers.uuid.Provider',
                'driver': 'keystone.token.persistence.backends.sql.Token',
            },
        }

        self.services = ['keystone']

    def init_before(self):
        self.package = env['cluster']['os_package_map']['keystone']
        self.prefix = self.package.get('prefix', '/opt/keystone')
        self.python = Python(self.prefix)

    def init_after(self):
        self.data.update({
            'tmp_admin_token': 'admin_token = {0}'.format(self.data['admin_token']),
        })

        if self.data['version'] == 'juno':
            self.client = 'keystone'
        else:
            self.client = 'openstack'

    def setup(self):
        data = self.init()
        version = data['version']

        if self.is_tag('package'):
            self.python.setup()
            self.python.setup_package(**self.package)

        is_updated = False
        if self.is_tag('conf'):
            is_updated = filer.template(
                '/etc/keystone/keystone.conf',
                src='{0}/keystone.conf.j2'.format(version),
                data=data,
            )

        if self.is_tag('data'):
            if env.host == env.hosts[0]:
                sudo('{0}/bin/keystone-manage db_sync'.format(self.prefix))

        if self.is_tag('service'):
            self.enable_services().start_services(pty=False)
            if is_updated:
                self.restart_services(pty=False)

        if self.is_tag('data') and env.host == env.hosts[0]:
            time.sleep(3)
            self.create_tenant('admin', 'Admin Project')
            self.create_role('admin')
            self.create_role('_member_')
            self.create_user(data['admin_user'], data['admin_password'],
                             [['admin', 'admin'], ['admin', '_member_']])

            self.create_tenant(data['service_tenant_name'], 'Service Project')
            self.create_user(data['service_user'], data['service_password'],
                             [['service', 'admin']])

            for name, service in data['services'].items():
                self.create_service(name, service)

        if self.is_tag('conf'):
            self.disable_admin_token()

    def disable_admin_token(self):
        data = self.init()
        data.update({
            'tmp_admin_token': '# admin_token ='
        })
        filer.template(
            '/etc/keystone/keystone.conf',
            src='{0}/keystone.conf.j2'.format(data['version']),
            data=data,
        )
        self.restart_services(pty=False)

    def cmd(self, cmd):
        # create users, roles, services
        with api.shell_env(
                OS_SERVICE_TOKEN=self.data['admin_token'],
                OS_SERVICE_ENDPOINT='http://localhost:35357/v2.0',
                OS_TOKEN=self.data['admin_token'],
                OS_URL='http://localhost:35357/v2.0',
                ):
            return run('openstack {0}'.format(cmd))

    def create_tenant(self, name, description):
        tenant_list = self.cmd('project list')
        if ' {0} '.format(name) not in tenant_list:
            self.cmd('project create --description="{1}" {0}'.format(
                name, description))

    def create_role(self, name):
        role_list = self.cmd('role list')
        if ' {0} '.format(name) not in role_list:
            self.cmd('role create {0}'.format(name))

    def create_user(self, name, password, tenant_roles):
        user_list = self.cmd('user list')
        if ' {0} '.format(name) not in user_list:
            self.cmd('user create --password={1} {0}'.format(name, password))
            for tenant_role in tenant_roles:
                self.cmd('role add --user={0} --project={1} {2}'.format(
                    name, tenant_role[0], tenant_role[1]))

    def create_service(self, name, service):
        service_list = self.cmd('service list')
        endpoint_list = self.cmd('endpoint list')
        if ' {0} '.format(name) not in service_list:
            self.cmd('service create --name={0} --description="{1[description]}" {1[type]}'.format(name, service))  # noqa

        if ' {0} '.format(name) not in endpoint_list:
            self.cmd('''endpoint create \\
            --publicurl={0[publicurl]} \\
            --internalurl={0[internalurl]} \\
            --adminurl={0[adminurl]} \\
            --region {0[region]} \\
            {0[type]}'''.format(service))
