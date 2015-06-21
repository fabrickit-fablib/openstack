# coding: utf-8

from fabkit import sudo, env, filer
from fablib import python
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

    def init_data(self):
        self.connection = openstack_util.get_mysql_connection(self.data)
        self.data.update({
            'keystone': env.cluster['keystone'],
            # 'database': {
            #     'connection': self.connection,
            # },
        })

    def setup(self):
        data = self.get_init_data()

        openstack_util.setup_common()

        self.install_packages()

        pkg = python.install_from_git(
            'horizon',
            'https://github.com/openstack/horizon.git -b stable/juno')

        if not filer.exists('/var/lib/horizon'):
            sudo('cp -r {0} /var/lib/horizon'.format(pkg['git_dir']))

        sudo('chown -R apache:apache /var/lib/horizon')

        is_updated = filer.template(
            '/var/lib/horizon/openstack_dashboard/local/local_settings.py',
            data=data,
        )

        is_updated = filer.template(
            '/etc/httpd/conf.d/horizon_httpd.conf',
            data=data,
        ) or is_updated

        self.enable_services().start_services(pty=False)
        if is_updated:
            self.restart_services(pty=False)
