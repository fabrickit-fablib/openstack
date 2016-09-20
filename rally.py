# coding: utf-8

from fabkit import env, sudo, filer
from fablib.python import Python
from fablib.base import SimpleBase


class Rally(SimpleBase):
    def __init__(self):
        self.data_key = 'rally'
        self.data = {
        }

        self.services = []

    def init_before(self):
        self.package = env['cluster']['os_package_map']['rally']
        self.prefix = self.package.get('prefix', '/opt/rally')
        self.python = Python(self.prefix)

    def init_after(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
        })

    def setup(self):
        data = self.init()

        if self.is_tag('package'):
            self.python.setup()
            self.python.setup_package(**self.package)

        if self.is_tag('conf'):
            # setup conf files
            filer.template(
                '/etc/rally/rally.conf',
                src='{0}/rally.conf.j2'.format(data['version']),
                data=data,
            )

            filer.template(
                '/etc/rally/rally-existing.json',
                src='{0}/rally-existing.json.j2'.format(data['version']),
                data=data,
            )

        if self.is_tag('data') and env.host == env.hosts[0]:
            sudo('rally deployment list | grep {0} || '
                 'rally deployment create --file=/etc/rally/rally-existing.json --name={0}'.format(
                     env.cluster['keystone']['service_region']))
