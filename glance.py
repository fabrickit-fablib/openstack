# coding: utf-8

from fabkit import env, sudo, filer, run
from fablib.python import Python
from tools import Tools
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
            'glance-api',
            'glance-registry',
        ]

    def init_before(self):
        self.package = env['cluster']['os_package_map']['glance']
        self.prefix = self.package.get('prefix', '/opt/glance')
        self.python = Python(self.prefix)
        self.tools = Tools(self.python)

    def init_after(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
        })

    def setup(self):
        data = self.init()

        if self.is_tag('package'):
            self.tools.setup()

            # developインストールだと依存解決できなくてコケる?
            self.python.install_from_git(**self.package)

            if not filer.exists('/usr/bin/glance-manage'):
                sudo('ln -s {0}/bin/glance-manage /usr/bin/'.format(self.prefix))

        if self.is_tag('conf'):
            # setup conf files
            is_updated = filer.template(
                '/etc/glance/glance-api.conf',
                src='{0}/glance-api.conf.j2'.format(data['version']),
                data=data,
            )

            is_updated = filer.template(
                '/etc/glance/glance-registry.conf',
                src='{0}/glance-registry.conf.j2'.format(data['version']),
                data=data,
            ) or is_updated

        if self.is_tag('data'):
            sudo('{0}/bin/glance-manage db_sync'.format(self.prefix))

        if self.is_tag('conf', 'service'):
            self.enable_services().start_services(pty=False)
            if is_updated:
                self.restart_services(pty=False)

        if self.is_tag('data'):
            self.register_images()

    def cmd(self, cmd):
        return self.tools.cmd('glance {0}'.format(cmd))

    def register_images(self):
        data = self.init()

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
                + ' --property "is-public=True"' \
                + ' --file {2}'
            self.cmd(create_cmd.format(image_name, image, image_file))
