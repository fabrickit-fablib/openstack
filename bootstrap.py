# coding:utf-8

from fabkit import sudo, env, run, Service, Editor
from fablib.python import Python
from fablib.base import SimpleBase
from fablib.repository import yum


class Bootstrap(SimpleBase):
    def init_before(self):
        self.package = env['cluster']['os_package_map']['os-tools']
        self.prefix = self.package.get('prefix', '/opt/os-tools')
        self.python = Python(self.prefix)

        self.packages = [
            'mysql-devel',
        ]

    def setup(self):
        self.init()

        sudo('setenforce 0')
        Editor('/etc/selinux/config').s('SELINUX=enforcing', 'SELINUX=disable')

        Service('firewalld').stop().disable()

        if self.is_tag('package'):
            yum.install_epel()
            yum.install_rdo()

            self.python.setup()
            self.python.setup_package(**self.package)

        if self.is_tag('conf'):
            self.dump_openstackrc

    def dump_openstackrc(self):
        keystone_data = env.cluster['keystone']
        run('''cat << _EOT_ > ~/openstackrc
    export OS_USERNAME=admin
    export OS_PASSWORD={0}
    export OS_TENANT_NAME=admin
    export OS_AUTH_URL={1}'''.format(
            keystone_data['admin_password'],
            keystone_data['services']['keystone']['adminurl']))
