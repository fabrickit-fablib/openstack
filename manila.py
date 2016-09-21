# coding: utf-8

from fabkit import *  # noqa
from fablib.python import Python
from fablib.base import SimpleBase
import utils


class Manila(SimpleBase):
    def __init__(self):
        self.data_key = 'manila'
        self.data = {
        }

        self.packages = [
            'nfs-utils',
            'nfs4-acl-tools',
            'rpcbind',
        ]

        self.services = [
            'manila-api',
            'manila-scheduler',
            'manila-share',
            'rpcbind',
            'nfs-server',
            # 'manila-data',
        ]

    def init_before(self):
        self.package = env['cluster']['os_package_map']['manila']
        self.prefix = self.package.get('prefix', '/opt/manila')
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
            self.install_packages()

            # nfs-kernel-server(ubuntuのnfs-server) がないといくつかの処理が失敗する
            # これは、ファイルに直書きされてるので、nfs-serverからシンボリックリンクを張って代用する
            # https://github.com/openstack/manila/blob/fb44a0a49e53ebd449bcf2fd6871b3556a149463/manila/share/drivers/helpers.py#L273
            nfs_kernel_server = '/usr/lib/systemd/system/nfs-kernel-server.service'
            if not filer.exists(nfs_kernel_server):
                sudo('ln -s /usr/lib/systemd/system/nfs-server.service {0}'.format(
                    nfs_kernel_server))

        if self.is_tag('conf'):
            # setup conf files
            if filer.template(
                    '/etc/manila/manila.conf',
                    src='{0}/manila.conf.j2'.format(data['version']),
                    data=data):
                self.handlers['restart_manila-*'] = True

        if self.is_tag('data') and env.host == env.hosts[0]:
            sudo('{0}/bin/manila-manage --config-file /etc/manila/manila.conf '
                 'db sync'.format(self.prefix))

            self.setup_lvm()

        if self.is_tag('conf', 'service'):
            self.enable_services().start_services(pty=False)
            self.exec_handlers()

        if self.is_tag('data') and env.host == env.hosts[0]:
            with api.warn_only():
                result = self.cmd('type-list | grep default_share_type')
                if result.return_code != 0:
                    self.cmd('type-create default_share_type false')

    def cmd(self, cmd):
        self.init()
        return utils.oscmd('manila {0}'.format(cmd))

    def setup_lvm(self):
        data = self.init()
        lvm_backend = None
        for backend in data['backends'].values():
            if backend['type'] == 'lvm':
                lvm_backend = backend

        if len(lvm_backend) == 0:
            return

        volume_group = lvm_backend['volume_group']

        Service('lvm2-lvmetad').start().enable()

        volume_path = '/tmp/{0}'.format(volume_group)
        if not filer.exists(volume_path):
            sudo('dd if=/dev/zero of={0} bs=1 count=0 seek=8G'.format(volume_path))

        free_loopdev = sudo('losetup -f')
        sudo('losetup -a | grep {0} || losetup {1} {0}'.format(volume_path, free_loopdev))
        loopdev = "`losetup -a | grep {0} | awk -F : '{{print $1}}'`".format(volume_path)
        sudo("pvscan | grep {0} || pvcreate {0}".format(loopdev))
        sudo('pvscan | grep {0} || vgcreate {0} {1}'.format(volume_group, loopdev))
