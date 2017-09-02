# coding: utf-8

from fabkit import sudo, env, filer
from fablib.base import SimpleBase


class Horizon(SimpleBase):
    def __init__(self, data=None):
        self.data_key = 'horizon'
        self.data = {
            'auth_strategy': 'keystone',
            'allowed_hosts': "['*']",
        }

        self.services = ['nginx', 'horizon-uwsgi']
        self.packages = {
            'CentOS Linux 7.*': [
                'horizon-12.0.0',
                'nginx',
            ],
            'Ubuntu 16.*': [
                'horizon=12.0.0*',
                'nginx',
            ],
        }

    def init_after(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
        })

    def setup(self):
        data = self.init()

        if self.is_tag('package'):
            self.install_packages()

        if self.is_tag('conf'):
            is_updated = filer.template(
                '/etc/horizon/local_settings.py',
                src='{0}/horizon/local_settings.py'.format(data['version']),
                data=data,
            )

            data.update({
                'httpd_port': 10080,
                'uwsgi_port': 10081,
            })

            if filer.template(
                '/etc/nginx/conf.d/uwsgi-horizon.conf',
                src='uwsgi-horizon-nginx.conf',
                data=data,
            ):
                self.handlers['restart_nginx'] = True

            # sudo('sh -c "cd {0}/lib/horizon/ && {1} manage.py collectstatic --noinput"'.format(
            #     self.prefix, self.python.get_cmd()))
            # sudo('sh -c "cd {0}/lib/horizon/ && {1} manage.py compress --force"'.format(
            #     self.prefix, self.python.get_cmd()))

        if self.is_tag('service'):
            self.enable_services().start_services(pty=False)
            if is_updated:
                self.restart_services(pty=False)
