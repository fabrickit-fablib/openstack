# coding:utf-8

import time
from fabkit import sudo, api, filer, user, run
from fablib.python import Python
from fablib.base import SimpleBase
import openstack_util


class Keystone(SimpleBase):
    def __init__(self, data=None):
        self.prefix = '/opt/keystone'
        self.data_key = 'keystone'
        self.data = {
            'user': 'keystone',
            'admin_token': 'ADMIN',
            'token': {
                'provider': 'keystone.token.providers.uuid.Provider',
                'driver': 'keystone.token.persistence.backends.sql.Token',
            },
        }
        self.python = Python(prefix=self.prefix, version='2.7')

        self.services = ['openstack-keystone']

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

        if self.is_package:
            user.add(data['user'])
            openstack_util.setup_common(self.python)

            keystone = self.python.install_from_git(
                'keystone', 'https://github.com/openstack/keystone.git -b stable/kilo')

            if not filer.exists('/etc/keystone'):
                sudo('cp -r {0}/etc/ /etc/keystone/'.format(keystone['git_dir']))
            if not filer.exists('/usr/bin/keystone-manage'):
                sudo('ln -s {0}/bin/keystone-manage /usr/bin/'.format(self.prefix))

            filer.mkdir('/var/log/keystone', owner='keystone:keystone')

        if self.is_conf:
            is_updated = filer.template(
                '/etc/keystone/keystone.conf',
                data=data,
            )

            option = ' --log-dir /var/log/keystone'
            is_updated = filer.template('/etc/init.d/openstack-keystone', '755',
                                        data={
                                            'prefix': self.prefix,
                                            'prog': 'keystone-all',
                                            'option': option,
                                            'config': '/etc/keystone/keystone.conf',
                                            'user': self.data['user'],
                                        },
                                        src_target='initscript') or is_updated

            self.enable_services().start_services(pty=False)
            if is_updated:
                self.restart_services(pty=False)

            time.sleep(3)  # 立ち上げてすぐにはLISTENしないので、3秒待つ

        if self.is_data:
            self.db_sync()

            self.create_project('admin', 'Admin Project')
            self.create_role('admin')
            self.create_role('_member_')
            self.create_user(data['admin_user'], data['admin_password'],
                             [['admin', 'admin'], ['admin', '_member_']])

            self.create_project(data['service_tenant_name'], 'Service Project')
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

    def cmd(self, cmd):
        # create users, roles, services
        with api.shell_env(
                OS_TOKEN=self.data['admin_token'],
                OS_URL='http://localhost:35357/v2.0'
                ):
            return run('{0}/bin/openstack {1}'.format(self.prefix, cmd))

    def create_project(self, name, description):
        project_list = self.cmd('project list')
        if ' {0} '.format(name) not in project_list:
            self.cmd('project create --description="{0}" {1}'.format(
                description, name))

    def create_role(self, name):
        role_list = self.cmd('role list')
        if ' {0} '.format(name) not in role_list:
            self.cmd('role create {0}'.format(name))

    def create_user(self, name, password, tenant_roles):
        user_list = self.cmd('user list')
        if ' {0} '.format(name) not in user_list:
            self.cmd('user create --password={0} {1}'.format(password, name))
            for tenant_role in tenant_roles:
                self.cmd('role add --user={0} --project={1} {2}'.format(
                    name, tenant_role[0], tenant_role[1]))

    def create_service(self, name, service):
        service_list = self.cmd('service list')
        endpoint_list = self.cmd('endpoint list')
        if ' {0} '.format(name) not in service_list:
            self.cmd('service create --name={0} --description="{1[description]}" {1[type]}'.format(name, service))  # noqa

        if name not in endpoint_list:
            self.cmd('''endpoint create \\
            --publicurl={0[publicurl]} \\
            --internalurl={0[internalurl]} \\
            --adminurl={0[adminurl]} \\
            --region RegionOne \\
            {0[type]}
            '''.format(service))

    def dump_openstackrc(self):
        data = self.get_init_data()
        openstack_util.dump_openstackrc(data)

    def db_sync(self):
        # db_sync
        if not openstack_util.show_tables(self.connection) == sorted([
            'access_token',
            'assignment',
            'consumer',  # added on kilo
            'credential',
            'domain',
            'endpoint',
            'endpoint_group',  # added on kilo
            'federation_protocol',  # added on kilo
            'group',
            'id_mapping',  # added on juno
            'identity_provider',  # added on kilo
            'idp_remote_ids',  # added on kilo
            'mapping',  # added on kilo
            'migrate_version',
            'policy',
            'policy_association',  # added on kilo
            'project',
            'project_endpoint',  # added on kilo
            'project_endpoint_group',  # added on kilo
            'region',
            'request_token',  # added on kilo
            'revocation_event',  # added on kilo
            'role',
            'sensitive_config',  # added on kilo
            'service',
            'service_provider',  # added on kilo
            'token',
            'trust',
            'trust_role',
            'user',
            'user_group_membership',
            'whitelisted_config',  # added on kilo
        ]):

            # python2.6 だとdb_sync時に以下の様な辞書型の内包表記によりsyntaxerrorとなるので、python2.7以上の必要がある
            # centos6.x だとpython2.6が入ってる、centos7 だとpython2.7が入っている
            # kwargs = {k: encodeutils.safe_decode(v) for k, v in six.iteritems(kwargs)}
            sudo('{0}/bin/keystone-manage db_sync'.format(self.prefix))
