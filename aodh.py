# coding: utf-8

import re
from fabkit import env, filer, sudo
from fablib.python import Python
from fablib.base import SimpleBase
import utils


class Aodh(SimpleBase):
    def __init__(self, enable_services=['.*']):
        self.data_key = 'aodh'
        self.data = {
        }

        default_services = [
            'aodh-api',
            'aodh-evaluator',
            'aodh-notifier',
            'aodh-listener',
        ]

        self.services = []
        for service in default_services:
            for enable_service in enable_services:
                if re.search(enable_service, service):
                    self.services.append(service)
                    break

    def init_before(self):
        self.package = env['cluster']['os_package_map']['aodh']
        self.prefix = self.package.get('prefix', '/opt/aodh')
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
            if filer.template(
                '/etc/aodh/aodh.conf',
                src='{0}/aodh.conf.j2'.format(data['version']),
                data=data,
            ):
                self.handlers['restart_aodh-*'] = True

        if self.is_tag('data') and env.host == env.hosts[0]:
            sudo('{0}/bin/aodh-dbsync'.format(self.prefix))

        if self.is_tag('conf', 'service'):
            self.enable_services().start_services(pty=False)
            self.exec_handlers()

    def cmd(self, cmd):
        return utils.oscmd('aodh {0}'.format(cmd))
