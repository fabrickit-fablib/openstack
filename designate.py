# coding: utf-8

from fabkit import env, sudo, filer
from fablib.python import Python
from fablib.base import SimpleBase
import utils


class Designate(SimpleBase):
    def __init__(self):
        self.data_key = 'designate'
        self.data = {
        }

        self.services = [
            'designate-api',
        ]

    def init_before(self):
        self.package = env['cluster']['os_package_map']['designate']
        self.prefix = self.package.get('prefix', '/opt/designate')
        self.python = Python(self.prefix)

    def init_after(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
            'my_ip': env.node['ip']['default_dev']['ip'],
        })

    def setup(self):
        data = self.init()

        if self.is_tag('package'):
            self.python.setup()
            self.python.setup_package(**self.package)

        if self.is_tag('conf'):
            # setup conf files
            if filer.template(
                    '/etc/designate/designate.conf',
                    src='{0}/designate.conf.j2'.format(data['version']),
                    data=data):
                self.handlers['restart_ironic-*'] = True

        if self.is_tag('data') and env.host == env.hosts[0]:
            sudo('{0}/bin/designate-manage database sync'.format(self.prefix))

        if self.is_tag('conf', 'service'):
            self.enable_services().start_services(pty=False)
            self.exec_handlers()

    def cmd(self, cmd):
        self.init()
        return utils.oscmd('designate {0}'.format(cmd))
