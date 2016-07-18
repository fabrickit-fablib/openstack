# coding:utf-8

from fabkit import sudo, env, run, Service, Editor
from fablib.python import Python
from fablib.base import SimpleBase


class Bootstrap(SimpleBase):
    def __init__(self):

        # 'https://repos.fedorapeople.org/repos/openstack/openstack-mitaka/rdo-release-mitaka-5.noarch.rpm'
        # 'https://repos.fedorapeople.org/repos/openstack/openstack-liberty/rdo-release-liberty-3.noarch.rpm'
        self.packages = {
            'CentOS Linux 7.*': [
                {
                    'name': 'rdo-release-mitaka-5.noarch',
                    'path': 'https://repos.fedorapeople.org/repos/openstack/openstack-mitaka/rdo-release-mitaka-5.noarch.rpm',  # noqa
                },
                'epel-release',
                'mysql-devel',
            ]
        }

    def init_before(self):
        self.package = env['cluster']['os_package_map']['os-tools']
        self.prefix = self.package.get('prefix', '/opt/os-tools')
        self.python = Python(self.prefix)

    def setup(self):
        self.init()

        sudo('setenforce 0')
        Editor('/etc/selinux/config').s('SELINUX=enforcing', 'SELINUX=disable')

        Service('firewalld').stop().disable()

        if self.is_tag('package'):
            self.install_packages()

            self.python.setup()
            self.python.setup_package(**self.package)

        if self.is_tag('conf'):
            self.dump_openstackrc

    def dump_openstackrc(self):
        keystone_data = env.cluster['keystone']
        sudo('''cat << _EOT_ > /root/openstackrc
    export OS_USERNAME=admin
    export OS_PASSWORD={0}
    export OS_TENANT_NAME=admin
    export OS_AUTH_URL={1}'''.format(
            keystone_data['admin_password'],
            keystone_data['services']['keystone']['adminurl']))
