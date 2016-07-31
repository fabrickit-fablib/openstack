# coding: utf-8

from fabkit import env, sudo, filer
from fablib.python import Python
from fablib.base import SimpleBase
import utils


class Ironic(SimpleBase):
    def __init__(self):
        self.data_key = 'ironic'
        self.data = {
        }

        self.services = [
            'ironic-api',
            'ironic-conductor',
        ]

    def init_before(self):
        self.package = env['cluster']['os_package_map']['ironic']
        self.prefix = self.package.get('prefix', '/opt/ironic')
        self.python = Python(self.prefix)

    def init_after(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
            'neutron': env.cluster['neutron'],
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
                    '/etc/ironic/ironic.conf',
                    src='{0}/ironic.conf.j2'.format(data['version']),
                    data=data):
                self.handlers['restart_ironic-*'] = True

        if self.is_tag('data') and env.host == env.hosts[0]:
            sudo('{0}/bin/ironic-dbsync --config-file /etc/ironic/ironic.conf '
                 'upgrade --revision head'.format(self.prefix))

        if self.is_tag('conf', 'service'):
            self.enable_services().start_services(pty=False)
            self.exec_handlers()

    def cmd(self, cmd):
        self.init()
        return utils.oscmd('ironic {0}'.format(cmd))
