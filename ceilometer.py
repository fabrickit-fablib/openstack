# coding: utf-8

from fabkit import env, filer, sudo
from fablib.python import Python
from fablib.base import SimpleBase
import utils


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
            is_updated = filer.template(
                '/etc/ceilometer/ceilometer.conf',
                src='{0}/ceilometer.conf.j2'.format(data['version']),
                data=data,
            )

            is_updated = filer.template(
                '/etc/ceilometer/pipeline.yaml',
                src='{0}/pipeline.yaml'.format(data['version']),
                data=data,
            ) or is_updated

        if self.is_tag('data') and env.host == env.hosts[0]:
            sudo('{0}/bin/ceilometer-dbsync'.format(self.prefix))

        if self.is_tag('conf', 'service'):
            self.enable_services().start_services(pty=False)
            if is_updated:
                self.restart_services(pty=False)

    def cmd(self, cmd):
        return utils.oscmd('ceilometer {0}'.format(cmd))
