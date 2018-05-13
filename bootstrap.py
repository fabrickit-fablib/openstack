# coding:utf-8

import re
from fabkit import sudo, env, filer, Service, Editor
from fablib.base import SimpleBase

RE_CENTOS7 = re.compile('CentOS Linux 7.*')
RE_UBUNTU16 = re.compile('Ubuntu 16.*')


class Bootstrap(SimpleBase):
    def __init__(self):

        self.packages = {
            'CentOS Linux 7.*': [
                'epel-release',
                'vim',
                'wget',
                'openstack-tools',
            ],
            'Ubuntu 16.*': [
                'vim',
                'openstack-tools',
            ]
        }

    def setup(self):
        self.init()

        if RE_CENTOS7.match(env.node['os']):
            sudo('setenforce 0')
            Editor('/etc/selinux/config').s('SELINUX=enforcing', 'SELINUX=disable')

            Service('firewalld').stop().disable()
            filer.template('/etc/yum.repos.d/openstack.repo')
            sudo('yum clean all')

        elif RE_UBUNTU16.match(env.node['os']):
            filer.template('/etc/apt/sources.list.d/openstack-aptrepo.list')
            sudo('apt-get update')

        if self.is_tag('package'):
            self.install_packages()

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
            keystone_data['service_map']['keystone']['adminurl']))

        sudo('''cat << _EOT_ > /root/openstackrcv3
export OS_USERNAME=admin
export OS_PASSWORD={0}
export OS_TENANT_NAME=admin
export OS_AUTH_URL={1}/v3
export OS_REGION_NAME={2}
export OS_VOLUME_API_VERSION=2
export OS_IDENTITY_API_VERSION=3
export OS_USER_DOMAIN_NAME=${{OS_USER_DOMAIN_NAME:-"Default"}}
export OS_PROJECT_DOMAIN_NAME=${{OS_PROJECT_DOMAIN_NAME:-"Default"}}'''.format(
            keystone_data['admin_password'],
            keystone_data['endpoint'],
            keystone_data['service_region']))
