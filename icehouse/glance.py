# coding: utf-8

from fabkit import env, sudo, user, filer
from fablib import python
import openstack_util
from fablib.base import SimpleBase


class Glance(SimpleBase):
    def __init__(self):
        self.data_key = 'glance'
        self.data = {
            'user': 'glance',
            'paste_deploy': {
                'flavor': 'keystone'
            }
        }

        self.services = [
            'openstack-glance-api',
            'openstack-glance-registry',
        ]

    def init_data(self):
        self.connection = openstack_util.get_mysql_connection(self.data)
        self.data.update({
            'keystone': env.cluster['keystone'],
            'database': {
                'connection': self.connection['str']
            },
        })

    def setup(self):
        data = self.get_init_data()

        openstack_util.setup_common()

        user.add(data['user'])
        sudo('pip install python-glanceclient')

        pkg = python.install_from_git(
            'glance',
            'https://github.com/openstack/glance.git -b stable/icehouse')
        filer.mkdir('/var/log/glance/', owner='{0}:{0}'.format(data['user']))

        if not filer.exists('/etc/glance'):
            sudo('cp -r {0}/etc/ /etc/glance/'.format(pkg['git_dir']))

        # setup conf files
        is_updated = filer.template(
            '/etc/glance/glance-api.conf',
            data=self.data,
        )

        is_updated = filer.template(
            '/etc/glance/glance-registry.conf',
            data=self.data,
        ) or is_updated

        is_updated = filer.template('/etc/init.d/openstack-glance-api', '755',
                                    data={
                                        'prog': 'glance-api',
                                        'config': '/etc/glance/$prog.conf',
                                        'user': self.data['user'],
                                    },
                                    src_target='initscript') or is_updated

        is_updated = filer.template('/etc/init.d/openstack-glance-registry', '755',
                                    data={
                                        'prog': 'glance-registry',
                                        'config': '/etc/glance/$prog.conf',
                                        'user': self.data['user'],
                                    },
                                    src_target='initscript') or is_updated

        self.db_sync()

        self.enable_services().start_services(pty=False)
        if is_updated:
            self.restart_services(pty=False)

        self.cmd('image-list')

    def cmd(self, cmd):
        return openstack_util.client_cmd('glance {0}'.format(cmd))

    def db_sync(self):
        if not openstack_util.show_tables(self.connection) == sorted([
            'image_locations', 'image_members', 'image_properties',
            'image_tags', 'images', 'migrate_version',
            'task_info', 'tasks'
        ]):
            sudo('glance-manage db_sync')
