# coding: utf-8

from fabkit import env, sudo, filer
from fablib.python import Python
from tools import Tools
from fablib.base import SimpleBase


class Cinder(SimpleBase):
    def __init__(self):
        self.data_key = 'cinder'
        self.data = {
            'user': 'cinder',
        }

        self.services = [
            'os-cinder-api',
            'os-cinder-volume',
            'os-cinder-scheduler',
        ]

    def init_before(self):
        self.package = env['cluster']['os_package_map']['cinder']
        self.prefix = self.package.get('prefix', '/opt/cinder')
        self.python = Python(self.prefix)
        self.tools = Tools(self.python)

    def init_after(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
        })

    def setup(self):
        data = self.init()

        self.tools.setup()

        self.python.install_from_git(**self.package)

        if not filer.exists('/usr/bin/cinder-manage'):
            sudo('ln -s {0}/bin/cinder-manage /usr/bin/'.format(self.prefix))

        # setup conf files
        is_updated = filer.template(
            '/etc/cinder/cinder.conf',
            src='{0}/cinder.conf.j2'.format(self.package['version']),
            data=data,
        )

        sudo('{0}/bin/cinder-manage db sync'.format(self.prefix))

        self.enable_services().start_services(pty=False)
        if is_updated:
            self.restart_services(pty=False)

        self.register_images()

    def cmd(self, cmd):
        return self.tools.cmd('cinder {0}'.format(cmd))
