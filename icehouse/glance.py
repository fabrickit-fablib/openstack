# coding: utf-8

from fabkit import env, sudo, user, Service, filer
from fablib import python
import openstack_util


class Glance():
    data = {
        'user': 'glance',
        'paste_deploy': {
            'flavor': 'keystone'
        }
    }

    def __init__(self, data=None):
        if data:
            self.data.update(data)
        else:
            self.data.update(env.cluster['glance'])

        self.keystone_data = env.cluster['keystone']

        self.user = user
        self.data.update({
            'keystone_authtoken': self.keystone_data,
            'database': {
                'data': self.data['database'],
                'connection': openstack_util.convert_mysql_connection(self.data['database'])
            },
        })
        self.api_service = Service('openstack-glance-api')
        self.registry_service = Service('openstack-glance-registry')

    def setup(self):
        is_updated = self.install()
        self.db_sync()

        self.api_service.enable().start(pty=False)
        self.registry_service.enable().start(pty=False)
        if is_updated:
            self.api_service.restart(pty=False)
            self.registry_service.restart(pty=False)

        self.cmd('image-list')

        return 0

    def cmd(self, cmd):
        return openstack_util.client_cmd('glance {0}'.format(cmd), self.keystone_data)

    def install(self):
        data = self.data
        openstack_util.setup_init()

        user.add(data['user'])

        sudo('pip install python-glanceclient')

        pkg = python.install_from_git(
            'glance',
            'https://github.com/openstack/glance.git -b stable/icehouse')
        filer.mkdir('/var/log/glance/', owner='{0}:{0}'.format(self.data['user']))

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

        return is_updated

    def db_sync(self):
        if not openstack_util.show_tables(self.data['database']['data']) == sorted([
            'image_locations', 'image_members', 'image_properties',
            'image_tags', 'images', 'migrate_version',
            'task_info', 'tasks'
        ]):
            sudo('glance-manage db_sync')
