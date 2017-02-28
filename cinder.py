# coding: utf-8

from fabkit import *  # noqa
from fablib.python import Python
from fablib.base import SimpleBase
import utils


class Cinder(SimpleBase):
    def __init__(self):
        self.data_key = 'cinder'
        self.data = {
            'user': 'cinder',
        }

        self.services = [
            'cinder-api',
            'cinder-volume',
            'cinder-scheduler',
            'target',
        ]

        self.packages = [
            'targetcli',
            'qemu-kvm',
            'lvm2'
        ]

    def init_before(self):
        self.package = env['cluster']['os_package_map']['cinder']
        self.prefix = self.package.get('prefix', '/opt/cinder')
        self.python = Python(self.prefix)

    def init_after(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
        })

    def setup(self):
        data = self.init()

        if self.is_tag('package'):
            self.install_packages()

            self.python.setup()
            self.python.setup_package(**self.package)

            self.setup_lvm()

        if self.is_tag('conf'):
            # setup conf files
            is_updated = filer.template(
                '/etc/cinder/cinder.conf',
                src='{0}/cinder/cinder.conf'.format(self.package['version']),
                data=data,
            )

        if self.is_tag('data'):
            sudo('{0}/bin/cinder-manage db sync'.format(self.prefix))

        if self.is_tag('service'):
            self.enable_services().start_services(pty=False)
            if is_updated:
                self.restart_services(pty=False)

    def cmd(self, cmd):
        return utils.oscmd('cinder {0}'.format(cmd))

    def setup_lvm(self):
        data = self.init()
        lvm_backend = None
        for backend in data['backends'].values():
            if backend['type'] == 'lvm':
                lvm_backend = backend

        if len(lvm_backend) == 0:
            return

        volume_group = lvm_backend['volume_group']
        filer.template('/etc/cinder/lvm.conf', data={
            'volume_group': volume_group,
        })

        Service('lvm2-lvmetad').start().enable()

        volume_path = '/tmp/{0}'.format(volume_group)
        if not filer.exists(volume_path):
            sudo('dd if=/dev/zero of={0} bs=1 count=0 seek=8G'.format(volume_path))

        free_loopdev = sudo('losetup -f')
        # if re.search(' {0} '.format(volume_group), result) == -1:
        sudo('losetup -a | grep {0} || losetup {1} {0}'.format(volume_path, free_loopdev))
        loopdev = "`losetup -a | grep {0} | awk -F : '{{print $1}}'`".format(volume_path)
        sudo("pvscan | grep {0} || pvcreate {0}".format(loopdev))
        sudo('pvscan | grep {0} || vgcreate {0} {1}'.format(volume_group, loopdev))
