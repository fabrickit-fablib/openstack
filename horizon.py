# coding: utf-8

from fabkit import sudo, env, filer
from fablib.python import Python
from tools import Tools
from fablib.base import SimpleBase


class Horizon(SimpleBase):
    def __init__(self, data=None):
        self.data_key = 'horizon'
        self.data = {
            'auth_strategy': 'keystone',
            'allowed_hosts': "['*']",
        }

        self.services = ['httpd', 'memcached']
        self.packages = ['httpd', 'mod_wsgi', 'memcached']

        # self.prefix = '/opt/horizon' にすると、インスタンスリスト表示時に以下のエラーが発生
        # self.prefix = '/usr' にすると発生しないので、OS依存のモジュール読み込みで失敗してそう
        # /opt/horizon/lib/python2.7/site-packages/_cffi_backend.so: undefined symbol: PyUnicodeUCS2_FromUnicode  # noqa
        # Exception Location: /opt/horizon/lib/python2.7/site-packages/cffi/api.py in __init__, line 56  # noqa

    def init_before(self):
        self.package = env['cluster']['os_package_map']['horizon']
        self.prefix = self.package.get('prefix', '/usr')
        self.python = Python(self.prefix, self.package.get('python', '2.7'))
        self.tools = Tools(self.python)

    def init_after(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
            'prefix': self.prefix,
        })

    def setup(self):
        data = self.init()

        if self.is_tag('package'):
            self.tools.setup()
            self.install_packages()

            self.python.install_from_git(**self.package)

            sudo('sh -c "cd {0}/lib/horizon/ && {1} manage.py collectstatic --noinput"'.format(
                self.prefix, self.python.get_cmd()))
            sudo('sh -c "cd {0}/lib/horizon/ && {1} manage.py compress --force"'.format(
                self.prefix, self.python.get_cmd()))

            sudo('chown -R apache:apache {0}/lib/horizon'.format(self.prefix))

        if self.is_tag('conf'):
            is_updated = filer.template(
                self.prefix + '/lib/horizon/openstack_dashboard/local/local_settings.py',
                src='{0}/local_settings.py.j2'.format(data['version']),
                data=data,
            )

            is_updated = filer.template(
                '/etc/httpd/conf.d/horizon_httpd.conf',
                src='{0}/horizon_httpd.conf.j2'.format(data['version']),
                data=data,
            ) or is_updated

        if self.is_tag('service'):
            self.enable_services().start_services(pty=False)
            if is_updated:
                self.restart_services(pty=False)
