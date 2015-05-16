# coding: utf-8

from fabkit import env, sudo, user, filer, run
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
            'https://github.com/openstack/glance.git -b stable/juno')

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

    def cmd(self, cmd):
        return openstack_util.client_cmd('glance {0}'.format(cmd))

    def register_images(self):
        data = self.get_init_data()

        result = self.cmd("image-list 2>/dev/null | grep '| ' | grep -v '| ID' | awk '{print $4}'")
        image_list = result.split('\r\n')

        for image_name, image in data['images'].items():
            if image_name in image_list:
                continue

            image_file = '/tmp/{0}'.format(image_name)
            if not filer.exists(image_file):
                run('wget {0} -O {1}'.format(image['url'], image_file))

            create_cmd = 'image-create --name "{0}" --disk-format {1[disk-format]}' \
                + ' --container-format {1[container-format]}' \
                + ' --is-public {1[is-public]} < {2}'
            self.cmd(create_cmd.format(image_name, image, image_file))

    def db_sync(self):
        if not openstack_util.show_tables(self.connection) == sorted([
            'image_locations',
            'image_members',
            'image_properties',
            'image_tags',
            'images',
            'metadef_namespace_resource_types',  # added on juno
            'metadef_namespaces',                # added on juno
            'metadef_objects',                   # added on juno
            'metadef_properties',                # added on juno
            'metadef_resource_types',            # added on juno
            'migrate_version',
            'task_info',
            'tasks'
        ]):

            sudo('glance-manage db_sync')
