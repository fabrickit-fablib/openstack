# coding: utf-8

from fabkit import sudo, env, filer
from fablib.python import Python
import openstack_util
from fablib.base import SimpleBase


class Horizon(SimpleBase):
    def __init__(self, data=None):
        self.data_key = 'horizon'
        self.data = {
            'auth_strategy': 'keystone',
            'allowed_hosts': "['*']",
        }

        self.services = ['httpd']
        self.packages = ['httpd', 'mod_wsgi']

        self.prefix = '/opt/horizon'
        self.python = Python(self.prefix, '2.7')

    def init_data(self):
        self.connection = openstack_util.get_mysql_connection(self.data)
        self.data.update({
            'keystone': env.cluster['keystone'],
            'prefix': self.prefix,
            # 'database': {
            #     'connection': self.connection,
            # },
        })

    def setup(self):
        data = self.init()

        openstack_util.setup_common(self.python)

        self.install_packages()

        pkg = self.python.install_from_git(
            'horizon',
            'https://github.com/openstack/horizon.git -b {0}'.format(data['branch']))

        if not filer.exists('/opt/horizon/lib/horizon'):
            sudo('cp -r {0} /opt/horizon/lib/horizon'.format(pkg['git_dir']))

        sudo('chown -R apache:apache /opt/horizon/lib/horizon')

        is_updated = filer.template(
            self.prefix + '/lib/horizon/openstack_dashboard/local/local_settings.py',
            data=data,
        )

        return
        is_updated = filer.template(
            '/etc/httpd/conf.d/horizon_httpd.conf',
            data=data,
        ) or is_updated

        self.enable_services().start_services(pty=False)
        if is_updated:
            self.restart_services(pty=False)
