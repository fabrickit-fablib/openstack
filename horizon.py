# coding: utf-8

from fabkit import sudo, env, filer
from fablib.python import Python
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

    def init_before(self):
        self.package = env['cluster']['os_package_map']['horizon']
        self.prefix = self.package.get('prefix', '/usr')
        self.python = Python(self.prefix)

    def init_after(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
            'prefix': self.prefix,
        })

    def setup(self):
        data = self.init()

        if self.is_tag('package'):
            self.install_packages()
            self.python.setup()
            self.python.setup_package(**self.package)

        if self.is_tag('conf'):
            is_updated = filer.template(
                self.prefix + '/lib/horizon/openstack_dashboard/local/local_settings.py',
                src='{0}/horizon/local_settings.py'.format(data['version']),
                data=data,
            )

            is_updated = filer.template(
                '/etc/httpd/conf.d/horizon_httpd.conf',
                src='{0}/horizon/httpd.conf'.format(data['version']),
                data=data,
            ) or is_updated

            sudo('sh -c "cd {0}/lib/horizon/ && {1} manage.py collectstatic --noinput"'.format(
                self.prefix, self.python.get_cmd()))
            sudo('sh -c "cd {0}/lib/horizon/ && {1} manage.py compress --force"'.format(
                self.prefix, self.python.get_cmd()))

            sudo('chown -R apache:apache {0}/lib/horizon'.format(self.prefix))

        if self.is_tag('data'):
            sudo('sh -c "cd {0}/lib/horizon/ && {1} manage.py syncdb --noinput"'.format(
                self.prefix, self.python.get_cmd()))

        if self.is_tag('service'):
            self.enable_services().start_services(pty=False)
            if is_updated:
                self.restart_services(pty=False)
