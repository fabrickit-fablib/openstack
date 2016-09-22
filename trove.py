# coding: utf-8

from fabkit import env, sudo, filer
from fablib.python import Python
from fablib.base import SimpleBase
from glance import Glance
import utils


class Trove(SimpleBase):
    def __init__(self):
        self.data_key = 'trove'
        self.data = {
        }

        self.services = [
            'trove-api',
            'trove-taskmanager',
            'trove-conductor',
        ]

    def init_before(self):
        self.package = env['cluster']['os_package_map']['trove']
        self.prefix = self.package.get('prefix', '/opt/trove')
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
                    '/etc/trove/trove.conf',
                    src='{0}/trove.conf.j2'.format(data['version']),
                    data=data):
                self.handlers['restart_trove-*'] = True

            if filer.template(
                    '/etc/trove/trove-taskmanager.conf',
                    src='{0}/trove-taskmanager.conf.j2'.format(data['version']),
                    data=data):
                self.handlers['restart_trove-*'] = True

            if filer.template(
                    '/etc/trove/trove-guestagent.conf',
                    src='{0}/trove-guestagent.conf.j2'.format(data['version']),
                    data=data):
                self.handlers['restart_trove-*'] = True

        if self.is_tag('data') and env.host == env.hosts[0]:
            sudo('{0}/bin/trove-manage db_sync'.format(self.prefix))
            self.register_image()

        if self.is_tag('conf', 'service'):
            self.enable_services().start_services(pty=False)
            self.exec_handlers()

    def cmd(self, cmd):
        self.init()
        return utils.oscmd('trove {0}'.format(cmd))

    def register_image(self):
        """
        trove images for ubuntu
        http://tarballs.openstack.org/trove/images/ubuntu/

        building guest images
        http://docs.openstack.org/developer/trove/dev/building_guest_images.html

        ```
        git clone https://github.com/openstack/trove-integration
        git clone https://github.com/openstack/tripleo-image-elements.git

        export PATH_TRIPLEO_ELEMENTS=$PWD/tripleo-image-elements
        export REDSTACK_SCRIPTS=$PWD/trove-integration/scripts
        export DIB_CLOUD_INIT_DATASOURCES="ConfigDrive"
        export ELEMENTS_PATH=$REDSTACK_SCRIPTS/files/elements:$PATH_TRIPLEO_ELEMENTS/elements

        disk-image-create -a amd64 -o ./ubuntu-percona.qemu ubuntu vm heat-cfntools \
            cloud-init-datasources ubuntu-guest ubuntu-mysql
        ```
        """
        glance = Glance()
        image_id = glance.create_image(
            'trove_mysql',
            'http://tarballs.openstack.org/trove/images/ubuntu/mysql.qcow2')

        sudo("/opt/trove/bin/trove-manage --config-file /etc/trove/trove.conf datastore_update mysql ''")  # noqa
        sudo("/opt/trove/bin/trove-manage --config-file /etc/trove/trove.conf datastore_version_update mysql mysql-5.6 mysql {0} '' 1".format(image_id))  # noqa
