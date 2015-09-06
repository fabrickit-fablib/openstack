# coding:utf-8

from fabkit import sudo, api, filer, user, run
from fablib.python import Python
from fablib.base import SimpleBase
import openstack_util


class Keystone(SimpleBase):
    def __init__(self, data=None):
        self.prefix = '/opt/keystone'
        self.python = Python(prefix=self.prefix, version='2.7')

        self.data_key = 'keystone'
        self.data = {
            'user': 'keystone',
            'admin_token': 'ADMIN',
            'token': {
                'provider': 'keystone.token.providers.uuid.Provider',
                'driver': 'keystone.token.persistence.backends.sql.Token',
            },
        }

        self.services = ['os-keystone']

    def init_data(self):
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

        if self.is_package:
            user.add(data['user'])
            openstack_util.setup_common(self.python)

            keystone = self.python.install_from_git(
                'keystone',
                'https://github.com/openstack/keystone.git -b {0}'.format(data['branch']),
                git_dir='/opt/ossrc/keystone',
                is_develop=True)

            if version == 'kilo':
                self.python.install('python-openstackclient')
                self.python.install('oslo.utils<1.5.0,>=1.4.0')
                self.python.install('oslo.config<1.10.0,>=1.9.3')
                self.python.install('python-keystoneclient<1.4.0,>=1.2.0')

                if not filer.exists('/usr/bin/openstack'):
                    sudo('ln -s {0}/bin/openstack /usr/bin/'.format(self.prefix))

            if not filer.exists('/etc/keystone'):
                sudo('cp -r {0}/etc/ /etc/keystone/'.format(keystone['git_dir']))
            if not filer.exists('/usr/bin/keystone-manage'):
                sudo('ln -s {0}/bin/keystone-manage /usr/bin/'.format(self.prefix))
            if not filer.exists('/usr/bin/keystone'):
                sudo('ln -s {0}/bin/keystone /usr/bin/'.format(self.prefix))

            filer.mkdir('/var/log/keystone', owner='keystone:keystone')

        if self.is_conf:
            is_updated = filer.template(
                '/etc/keystone/keystone.conf',
                src='{0}/keystone.conf.j2'.format(version),
                data=data,
            )

            option = '--config-file /etc/keystone/keystone.conf --log-dir /var/log/keystone'
            is_updated = filer.template('/etc/systemd/system/os-keystone.service',
                                        '755', data={
                                            'prefix': self.prefix,
                                            'prog': 'keystone-all',
                                            'option': option,
                                            'user': self.data['user'],
                                        },
                                        src='systemd.service')

            self.enable_services().start_services(pty=False)
            if is_updated:
                self.restart_services(pty=False)

        if self.is_data:
            sudo('{0}/bin/keystone-manage db_sync'.format(self.prefix))
            print version

            if version == 'juno':
                self.create_tenant('admin', 'Admin Tenant')
                self.create_role('admin')
                self.create_role('_member_')
                self.create_user(data['admin_user'], data['admin_password'],
                                 [['admin', 'admin'], ['admin', '_member_']])

                self.create_tenant(data['service_tenant_name'], 'Service Tenant')
                self.create_user(data['service_user'], data['service_password'],
                                 [['service', 'admin']])

                for name, service in data['services'].items():
                    self.create_service(name, service)

            elif version == 'kilo':
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
            return run('{0}/bin/{1} {2}'.format(self.prefix, self.client, cmd))

    def create_tenant(self, name, description):
        if self.client == 'keystone':
            tenant_list = self.cmd('tenant-list')
            if ' {0} '.format(name) not in tenant_list:
                self.cmd('tenant-create --name={0} --description="{1}"'.format(
                    name, description))

        elif self.client == 'openstack':
            tenant_list = self.cmd('project list')
            if ' {0} '.format(name) not in tenant_list:
                self.cmd('project create --description="{1}" {0}'.format(
                    name, description))

    def create_role(self, name):
        if self.client == 'keystone':
            role_list = self.cmd('role-list')
            if ' {0} '.format(name) not in role_list:
                self.cmd('role-create --name={0}'.format(name))
        elif self.client == 'openstack':
            role_list = self.cmd('role list')
            if ' {0} '.format(name) not in role_list:
                self.cmd('role create {0}'.format(name))

    def create_user(self, name, password, tenant_roles):
        if self.client == 'keystone':
            user_list = self.cmd('user-list')
            if ' {0} '.format(name) not in user_list:
                self.cmd('user-create --name={0} --pass={1}'.format(name, password))
                for tenant_role in tenant_roles:
                    self.cmd('user-role-add --user={0} --tenant={1} --role={2}'.format(
                        name, tenant_role[0], tenant_role[1]))
        elif self.client == 'openstack':
            user_list = self.cmd('user list')
            if ' {0} '.format(name) not in user_list:
                self.cmd('user create --password={1} {0}'.format(name, password))
                for tenant_role in tenant_roles:
                    self.cmd('role add --user={0} --project={1} {2}'.format(
                        name, tenant_role[0], tenant_role[1]))

    def create_service(self, name, service):
        if self.client == 'keystone':
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
        elif self.client == 'openstack':
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

    def dump_openstackrc(self):
        data = self.init()
        openstack_util.dump_openstackrc(data)
