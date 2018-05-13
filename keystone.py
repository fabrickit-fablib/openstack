# coding:utf-8

import re
import time
from fabkit import sudo, filer, env, api
from fablib.base import SimpleBase
import utils

RE_UBUNTU = re.compile('Ubuntu.*')


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

        self.services = [
            'nginx',
            'keystone-admin-uwsgi',
            'keystone-public-uwsgi',
        ]

        self.packages = {
            'CentOS Linux 7.*': ['nginx'],
            'Ubuntu 16.*': ['nginx'],
        }

    def init_before(self):
        self.version = env.cluster[self.data_key]['version']
        if self.version == 'master':
            self.packages['CentOS Linux 7.*'].extend([
                'keystone-14.0.0.0b1',
            ])
            self.packages['Ubuntu 16.*'].extend([
                'keystone=14.0.0.0b1',
            ])
        elif self.version == 'pike':
            self.packages['CentOS Linux 7.*'].extend([
                'keystone-12.0.0',
            ])
            self.packages['Ubuntu 16.*'].extend([
                'keystone=12.0.0*',
            ])

    def init_after(self):
        self.data.update({
            'tmp_admin_token': 'admin_token = {0}'.format(self.data['admin_token']),
        })

        self.client = 'openstack'

    def setup(self):
        data = self.init()

        if self.is_tag('package'):
            if RE_UBUNTU.match(env.node['os']):
                with api.warn_only():
                    self.install_packages()
                    sudo('rm -rf /etc/nginx/sites-available/default')
            else:
                self.install_packages()
                filer.template('/usr/lib/systemd/system/keystone-public-uwsgi.service')
                filer.template('/usr/lib/systemd/system/keystone-admin-uwsgi.service')
                sudo('systemctl daemon-reload')

        if self.is_tag('conf'):
            if filer.template(
                '/etc/keystone/keystone.conf',
                src='{0}/keystone/keystone.conf'.format(self.version),
                data=data,
                    ):
                self.handlers['restart_keystone-public'] = True
                self.handlers['restart_keystone-admin'] = True

            if RE_UBUNTU.match(env.node['os']):
                nginx_user = 'www-data'
            else:
                nginx_user = 'nginx'

            if filer.template(
                '/etc/nginx/nginx.conf',
                data={
                    'user': nginx_user
                },
            ):
                self.handlers['restart_nginx'] = True

            # For keystone public
            data.update({
                'httpd_port': data['public_port'],
                'uwsgi_socket': '/var/run/keystone-public-uwsgi.sock',
            })

            if filer.template(
                '/etc/keystone/keystone-public-uwsgi.ini',
                data=data,
            ):
                self.handlers['restart_keystone-public-uwsgi'] = True

            if filer.template(
                '/etc/nginx/conf.d/keystone-public-uwsgi.conf',
                src='uwsgi-nginx.conf',
                data=data,
            ):
                self.handlers['restart_nginx'] = True

            # For admin conf
            data.update({
                'httpd_port': data['admin_port'],
                'uwsgi_socket': '/var/run/keystone-admin-uwsgi.sock',
            })

            if filer.template(
                '/etc/keystone/keystone-admin-uwsgi.ini',
                data=data,
            ):
                self.handlers['restart_keystone-admin-uwsgi'] = True

            if filer.template(
                '/etc/nginx/conf.d/keystone-admin-uwsgi.conf',
                src='uwsgi-nginx.conf',
                data=data,
            ):
                self.handlers['restart_nginx'] = True

        if self.is_tag('data'):
            sudo('/opt/keystone/bin/keystone-manage db_sync')

            sudo('/opt/keystone/bin/keystone-manage fernet_setup '
                 '--keystone-user root --keystone-group root ')
            sudo('/opt/keystone/bin/keystone-manage credential_setup '
                 '--keystone-user root --keystone-group root ')

            sudo('/opt/keystone/bin/keystone-manage bootstrap --bootstrap-password {0} '
                 '--bootstrap-admin-url {1[adminurl]} '
                 '--bootstrap-internal-url {1[internalurl]} '
                 '--bootstrap-public-url {1[publicurl]} '
                 '--bootstrap-region-id {1[region]}'.format(
                     data['admin_password'], data['service_map']['keystone']))

            sudo('chown -R root:root /etc/keystone/fernet-keys/')
            sudo('chown -R root:root /etc/keystone/credential-keys/')

        if self.is_tag('service'):
            self.enable_services().start_services(pty=False)
            self.exec_handlers()

        if self.is_tag('data') and env.host == env.hosts[0]:
            time.sleep(3)
            self.create_tenant(data['service_tenant_name'], 'Service Project')
            self.create_user(data['service_user'], data['service_password'],
                             [['service', 'admin']])

            for name, service in data['service_map'].items():
                self.create_service(name, service)

    def cmd(self, cmd):
        self.init()
        return utils.oscmd('openstack {0}'.format(cmd))

    def create_tenant(self, name, description):
        self.init()
        tenant_list = self.cmd('project list')
        if ' {0} '.format(name) not in tenant_list:
            self.cmd('project create --description="{1}" {0}'.format(
                name, description))

    def create_role(self, name):
        self.init()
        role_list = self.cmd('role list')
        if ' {0} '.format(name) not in role_list:
            self.cmd('role create {0}'.format(name))

    def create_user(self, name, password, tenant_roles):
        self.init()
        user_list = self.cmd('user list')
        if ' {0} '.format(name) not in user_list:
            self.cmd('user create --password={1} {0}'.format(name, password))
            for tenant_role in tenant_roles:
                self.cmd('role add --user={0} --project={1} {2}'.format(
                    name, tenant_role[0], tenant_role[1]))

    def create_service(self, name, service):
        self.init()
        service_list = self.cmd('service list')
        endpoint_list = self.cmd('endpoint list')
        if ' {0} '.format(name) not in service_list:
            self.cmd('service create --name={0} --description="{1[description]}" {1[type]}'.format(name, service))  # noqa

        if ' {0} '.format(name) not in endpoint_list:
            utils.oscmd('openstack endpoint create --region {0[region]}'
                        ' {0[type]} public {0[publicurl]};'
                        'openstack endpoint create --region {0[region]}'
                        ' {0[type]} internal {0[internalurl]};'
                        'openstack endpoint create --region {0[region]}'
                        ' {0[type]} admin {0[adminurl]};'.format(service))
