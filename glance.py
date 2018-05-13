# coding: utf-8

import re

from fabkit import env, sudo, filer, run
from fablib.base import SimpleBase
import utils

RE_UBUNTU = re.compile('Ubuntu.*')


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
            'nginx',
            'glance-api-uwsgi',
            'glance-registry',
        ]

        self.packages = {
            'CentOS Linux 7.*': ['nginx'],
            'Ubuntu 16.*': ['nginx'],
        }

    def init_before(self):
        self.version = env.cluster[self.data_key]['version']

        if self.version == 'master':
            self.packages['CentOS Linux 7.*'].extend([
                'glance-17.0.0.0b1',
            ])
            self.packages['Ubuntu 16.*'].extend([
                'glance=17.0.0.0b1',
            ])
        elif self.version == 'pike':
            self.packages['CentOS Linux 7.*'].extend([
                'glance-15.0.0',
            ])
            self.packages['Ubuntu 16.*'].extend([
                'glance=15.0.0*',
            ])

    def init_after(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
        })

    def setup(self):
        data = self.init()

        if self.is_tag('package'):
            self.install_packages()

            filer.mkdir(data['glance_store']['filesystem_store_datadir'])
            filer.template('/usr/lib/systemd/system/glance-api-uwsgi.service')
            sudo('systemctl daemon-reload')

        if self.is_tag('conf'):
            # setup conf files
            if filer.template(
                    '/etc/glance/glance-api.conf',
                    src='{0}/glance/glance-api.conf'.format(data['version']),
                    data=data):
                self.handlers['restart_glance-api'] = True

            if filer.template(
                    '/etc/glance/glance-registry.conf',
                    src='{0}/glance/glance-registry.conf'.format(data['version']),
                    data=data):
                self.handlers['restart_glance-registry'] = True

            data.update({
                'httpd_port': data['api_port'],
                'uwsgi_socket': '/var/run/glance-api-uwsgi.sock',
            })

            if filer.template(
                '/etc/glance/glance-api-uwsgi.ini',
                data=data,
            ):
                self.handlers['restart_glance-api-uwsgi'] = True

        if self.is_tag('data') and env.host == env.hosts[0]:
            sudo('/opt/glance/bin/glance-manage db_sync')

        if self.is_tag('conf', 'service'):
            self.enable_services().start_services(pty=False)
            self.exec_handlers()

    def cmd(self, cmd):
        self.init()
        return utils.oscmd('openstack {0}'.format(cmd))

    def create_image(self, image_name, image_url, disk_format='qcow2', container_format='bare',
                     property='is_public=True'):
        self.init()

        result = self.cmd(
            "image list 2>/dev/null | grep ' {0} ' | awk '{{print $2}}'".format(image_name))

        if len(result) > 0:
            return result

        image_file = '/tmp/{0}'.format(image_name)
        if not filer.exists(image_file):
            run('wget {0} -O {1}'.format(image_url, image_file))

        create_cmd = 'image create --disk-format {0}' \
            + ' --container-format {1}' \
            + ' --file {2} {3}'
        result = self.cmd(create_cmd.format(
            disk_format, container_format, image_file, image_name))

        result = self.cmd(
            "image list 2>/dev/null | grep ' {0} ' | awk '{{print $2}}'".format(image_name))

        if len(result) > 0:
            return result

        raise Exception('Failed Create Image: {0}'.format(image_name))
