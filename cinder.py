# coding: utf-8

from fabkit import *  # noqa
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
            'cinder-scheduler',
            'cinder-volume',
            'target',
        ]

        self.packages = {
            'CentOS Linux 7.*': [
                'cinder-11.0.0.0b2',
                'targetcli',
                'lvm2',
                'qemu-2.9.0',
            ],
            'Ubuntu 16.*': [
                'cinder=11.0*',
                'targetcli',
                'qemu',
            ],
        }

    def init_after(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
        })

    def setup(self):
        data = self.init()
        version = data['version']

        if self.is_tag('package'):
            self.install_packages()

            self.setup_lvm()

        if self.is_tag('conf'):
            # setup conf files
            is_updated = filer.template(
                '/etc/cinder/cinder.conf',
                src='{0}/cinder/cinder.conf'.format(version),
                data=data,
            )

        if self.is_tag('data'):
            sudo('/opt/cinder/bin/cinder-manage db sync')

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
