# coding: utf-8

import re
from fabkit import env, filer, sudo
from fablib.python import Python
from fablib.base import SimpleBase
import utils


class Ceilometer(SimpleBase):
    def __init__(self, enable_services=['.*']):
        self.data_key = 'ceilometer'
        self.data = {
        }

        default_services = [
            'ceilometer-api',
            'ceilometer-collector',
            'ceilometer-agent-notification',
            'ceilometer-agent-compute',
            'ceilometer-agent-central',
            # 'ceilometer-alarm-evaluator', # liberty
            # 'ceilometer-alarm-notifier', # liberty
        ]

        self.services = []
        for service in default_services:
            for enable_service in enable_services:
                if re.search(enable_service, service):
                    self.services.append(service)
                    break

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
