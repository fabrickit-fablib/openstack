# coding: utf-8

from fabkit import env, sudo, filer
from fablib.python import Python
from tools import Tools
from fablib.base import SimpleBase


class Ceilometer(SimpleBase):
    def __init__(self):
        self.data_key = 'ceilometer'
        self.data = {
        }

        self.services = [
        ]

    def init_before(self):
        self.package = env['cluster']['os_package_map']['ceilometer']
        self.prefix = self.package.get('prefix', '/opt/ceilometer')
        self.python = Python(self.prefix)
        self.tools = Tools(self.python)

    def init_after(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
        })

    def setup(self):
        data = self.init()

        if self.is_tag('package'):
            self.tools.setup()

            # developインストールだと依存解決できなくてコケる?
            self.python.install_from_git(**self.package)

        if self.is_tag('conf'):
            # setup conf files
            is_updated = filer.template(
                '/etc/glance/glance-api.conf',
                src='kilo/glance-api.conf.j2'.format(data['version']),
                data=data,
            )

            is_updated = filer.template(
                '/etc/glance/glance-registry.conf',
                src='kilo/glance-registry.conf.j2'.format(data['version']),
                data=data,
            ) or is_updated

        if self.is_tag('data'):
            sudo('{0}/bin/glance-manage db_sync'.format(self.prefix))

        if self.is_tag('conf', 'service'):
            self.enable_services().start_services(pty=False)
            if is_updated:
                self.restart_services(pty=False)

        if self.is_tag('data'):
            self.register_images()

    def cmd(self, cmd):
        return self.tools.cmd('ceilometer {0}'.format(cmd))
