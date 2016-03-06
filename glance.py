# coding: utf-8

from fabkit import env, sudo, filer, run
from fablib.python import Python
from fablib.base import SimpleBase
import utils


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

    def init_after(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
        })

    def setup(self):
        data = self.init()

        if self.is_tag('package'):
            self.python.setup()
            self.python.setup_package(**self.package)

            filer.mkdir(data['glance_store']['filesystem_store_datadir'])

        if self.is_tag('conf'):
            # setup conf files
            if filer.template(
                    '/etc/glance/glance-api.conf',
                    src='{0}/glance-api.conf.j2'.format(data['version']),
                    data=data):
                self.handlers['restart_glance-api'] = True

            if filer.template(
                    '/etc/glance/glance-registry.conf',
                    src='{0}/glance-registry.conf.j2'.format(data['version']),
                    data=data):
                self.handlers['restart_glance-registry'] = True

        if self.is_tag('data') and env.host == env.hosts[0]:
            sudo('{0}/bin/glance-manage db_sync'.format(self.prefix))

        if self.is_tag('conf', 'service'):
            self.enable_services().start_services(pty=False)
            self.exec_handlers()

    def cmd(self, cmd):
        self.init()
        return utils.oscmd('glance {0}'.format(cmd))

    def create_image(self, image_name, image_url, disk_format='qcow2', container_format='bare',
                     property='is_public=True'):
        self.init()

        result = self.cmd(
            "image-list 2>/dev/null | grep ' {0} ' | awk '{{print $2}}'".format(image_name))

        if len(result) > 0:
            return result

        image_file = '/tmp/{0}'.format(image_name)
        if not filer.exists(image_file):
            run('wget {0} -O {1}'.format(image_url, image_file))

        create_cmd = 'image-create --name "{0}" --disk-format {1}' \
            + ' --container-format {2}' \
            + ' --property "{3}"' \
            + ' --file {4}'
        result = self.cmd(create_cmd.format(
            image_name, disk_format, container_format, property, image_file))

        result = self.cmd(
            "image-list 2>/dev/null | grep ' {0} ' | awk '{{print $2}}'".format(image_name))

        if len(result) > 0:
            return result

        raise Exception('Failed Create Image: {0}'.format(image_name))
