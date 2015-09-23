# coding: utf-8

from fabkit import run, api, Package, env, filer, sudo
from fablib.repository import yum
from fablib.python import Python
from fablib.base import SimpleBase


class Tools(SimpleBase):
    def __init__(self, os_python=None):
        self.os_python = os_python

    def init_before(self):
        self.package = env['cluster']['os_package_map']['tools']
        self.prefix = self.package.get('prefix', '/opt/os-tools')
        self.python = Python(self.prefix)

    def setup(self):
        self.init()
        yum.install_epel()
        yum.install_rdo()

        if self.is_tag('package'):
            self.setup_python(self.python)

            for client in self.package['clients']:
                self.python.install(client['package'])

                if not filer.exists('/usr/bin/{0}'.format(client['cmd'])):
                    sudo('ln -s {0}/bin/{1} /usr/bin/'.format(self.prefix, client['cmd']))

            if self.os_python:
                self.setup_python(self.os_python)

    def setup_python(self, python):
        python.setup()
        Package('mysql-devel').install()
        Package('mysql').install()
        python.install('mysql-python')
        # SQLAlchemy==0.9.10 is bad sql
        python.install('SQLAlchemy==0.9.8')

    def cmd(self, cmd):
        keystone = env.cluster['keystone']
        with api.shell_env(
            OS_USERNAME='admin',
            OS_PASSWORD=keystone['admin_password'],
            OS_TENANT_NAME='admin',
            OS_AUTH_URL=keystone['services']['keystone']['adminurl'],
        ):
            return run(cmd)

    def dump_openstackrc(self, keystone_data):
        run('''cat << _EOT_ > ~/openstackrc
    export OS_USERNAME=admin
    export OS_PASSWORD={0}
    export OS_TENANT_NAME=admin
    export OS_AUTH_URL={1}'''.format(
            keystone_data['admin_password'],
            keystone_data['services']['keystone']['adminurl']))
