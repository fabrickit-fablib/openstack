# coding: utf-8

from fabkit import env, sudo, filer
from fablib.python import Python
from tools import Tools
from fablib.base import SimpleBase


class Heat(SimpleBase):
    def __init__(self):
        self.data_key = 'heat'
        self.data = {
        }

        self.services = [
            'heat-api',
            'heat-engine',
        ]

    def init_before(self):
        self.package = env['cluster']['os_package_map']['heat']
        self.prefix = self.package.get('prefix', '/opt/heat')
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
                '/etc/heat/heat.conf',
                src='{0}/heat.conf.j2'.format(data['version']),
                data=data,
            )

        if self.is_tag('data'):
            self.tools.cmd('/opt/heat/bin/heat-keystone-setup-domain \
                            --stack-user-domain-name {0} \
                            --stack-domain-admin {1} \
                            --stack-domain-admin-password {2}'.format(
                self.data['stack_user_domain_name'],
                self.data['stack_domain_admin'],
                self.data['stack_domain_admin_password']))

            sudo('{0}/bin/heat-manage db_sync'.format(self.prefix))

        if self.is_tag('conf', 'service'):
            self.enable_services().start_services(pty=False)
            if is_updated:
                self.restart_services(pty=False)

    def cmd(self, cmd):
        return self.tools.cmd('heat {0}'.format(cmd))
