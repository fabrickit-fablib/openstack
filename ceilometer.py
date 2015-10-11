# coding: utf-8

from fabkit import env, filer, sudo
from fablib.python import Python
from tools import Tools
from fablib.base import SimpleBase


class Ceilometer(SimpleBase):
    def __init__(self):
        self.data_key = 'ceilometer'
        self.data = {
        }

        self.services = [
            'ceilometer-agnet-notification',
            'ceilometer-alarm-evaluator',
            'ceilometer-alarm-notifier',
            'ceilometer-api',
            'ceilometer-collector',
            'ceilometer-polling',
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
            self.python.install_from_git(**self.package)

        if self.is_tag('conf'):
            is_updated = filer.template(
                '/etc/ceilometer/ceilometer.conf',
                src='{0}/ceilometer.conf.j2'.format(data['version']),
                data=data,
            )

        if self.is_tag('data'):
            sudo('{0}/bin/ceilometer-dbsync'.format(self.prefix))

        if self.is_tag('conf', 'service'):
            self.enable_services().start_services(pty=False)
            if is_updated:
                self.restart_services(pty=False)

    def cmd(self, cmd):
        return self.tools.cmd('ceilometer {0}'.format(cmd))
