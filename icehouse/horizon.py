# coding: utf-8

from fabkit import sudo, env, Service, Package, filer
from fablib import python
import openstack_util


class Horizon():
    data = {
        'auth_strategy': 'keystone',
        'allowed_hosts': "['*']",
    }

    def __init__(self, data=None):
        if data:
            self.data.update(data)
        else:
            self.data.update(env.cluster['horizon'])

        self.keystone_data = env.cluster['keystone']
        self.data.update({
            'keystone_authtoken': self.keystone_data,
        })

        self.httpd = Service('httpd')

    def setup(self):
        is_updated = self.install()
        self.httpd.enable().start(pty=False)

        if is_updated:
            self.httpd.restart(pty=False)

        return 0

    def install(self):
        openstack_util.setup_init()

        Package('httpd').install()
        Package('mod_wsgi').install()

        pkg = python.install_from_git(
            'horizon',
            'https://github.com/openstack/horizon.git -b stable/icehouse')

        if not filer.exists('/var/lib/horizon'):
            sudo('cp -r {0} /var/lib/horizon'.format(pkg['git_dir']))

        sudo('chown -R apache:apache /var/lib/horizon')

        is_updated = filer.template(
            '/var/lib/horizon/openstack_dashboard/local/local_settings.py',
            data=self.data,
        )

        is_updated = filer.template(
            '/etc/httpd/conf.d/horizon_httpd.conf',
            data=self.data,
        ) or is_updated

        return is_updated
