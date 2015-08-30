# coding: utf-8

from fabkit import env, sudo, user, filer, run
from fablib.python import Python
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
            'os-glance-api',
            'os-glance-registry',
        ]

        self.prefix = '/opt/glance'
        self.python = Python(self.prefix, '2.7')

    def init_data(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
        })

    def setup(self):
        data = self.init()

        openstack_util.setup_common(self.python)

        user.add(data['user'])

        self.python.install('python-glanceclient')
        pkg = self.python.install_from_git(
            'glance',
            'https://github.com/openstack/glance.git -b {0}'.format(data['branch']))

        filer.mkdir('/var/log/glance/', owner='{0}:{0}'.format(data['user']))
        sudo('chown -R {0}:{0} /var/log/glance/'.format(data['user']))
        filer.mkdir('/var/lib/glance/images', owner='{0}:{0}'.format(data['user']))

        if not filer.exists('/etc/glance'):
            sudo('cp -r {0}/etc/ /etc/glance/'.format(pkg['git_dir']))
        if not filer.exists('/usr/bin/glance'):
            sudo('ln -s {0}/bin/glance /usr/bin/'.format(self.prefix))
        if not filer.exists('/usr/bin/glance-manage'):
            sudo('ln -s {0}/bin/glance-manage /usr/bin/'.format(self.prefix))

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

        option = '--config-file /etc/glance/glance-api.conf'
        is_updated = filer.template('/etc/systemd/system/os-glance-api.service',
                                    '755', data={
                                        'prefix': self.prefix,
                                        'prog': 'glance-api',
                                        'option': option,
                                        'user': data['user'],
                                    },
                                    src='systemd.service') or is_updated

        option = '--config-file /etc/glance/glance-registry.conf'
        is_updated = filer.template('/etc/systemd/system/os-glance-registry.service',
                                    '755', data={
                                        'prefix': self.prefix,
                                        'prog': 'glance-registry',
                                        'option': option,
                                        'user': data['user'],
                                    },
                                    src='systemd.service') or is_updated

        sudo('{0}/bin/glance-manage db_sync'.format(self.prefix))

        self.enable_services().start_services(pty=False)
        if is_updated:
            self.restart_services(pty=False)

    def cmd(self, cmd):
        return openstack_util.client_cmd('glance {0}'.format(cmd))

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
                + ' --is-public {1[is-public]} < {2}'
            self.cmd(create_cmd.format(image_name, image, image_file))
