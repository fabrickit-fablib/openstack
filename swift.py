# coding: utf-8

from fabkit import env, sudo, filer
from fablib.python import Python
from fablib.base import SimpleBase
import utils


class Swift(SimpleBase):
    def __init__(self):
        self.data_key = 'swift'
        self.data = {
        }

        self.services = [
            'swift-proxy-server',
            'swift-account-server',
            'swift-account-auditor',
            'swift-account-reaper',
            'swift-account-replicator',
            'swift-container-server',
            'swift-container-auditor',
            'swift-container-replicator',
            'swift-container-updater',
            'swift-object-server',
            'swift-object-auditor',
            'swift-object-replicator',
            'swift-object-updater',
        ]

    def init_before(self):
        self.package = env['cluster']['os_package_map']['swift']
        self.prefix = self.package.get('prefix', '/opt/swift')
        self.python = Python(self.prefix)

    def init_after(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
        })

        servers = ':11211,'.join(self.data['memcache_servers']) + ':11211'
        self.data['memcache_servers'] = servers

    def setup(self):
        data = self.init()

        if self.is_tag('package'):
            self.python.setup()
            self.python.setup_package(**self.package)

        if self.is_tag('conf'):
            # setup conf files
            if filer.template(
                    '/etc/swift/swift.conf',
                    src='{0}/swift/swift.conf.j2'.format(data['version']),
                    data=data):
                self.handlers['restart_swift-proxy-server'] = True

            if filer.template(
                    '/etc/swift/proxy-server.conf',
                    src='{0}/swift/proxy-server.conf.j2'.format(data['version']),
                    data=data):
                self.handlers['restart_swift-proxy-server'] = True

            if filer.template(
                    '/etc/swift/account-server.conf',
                    src='{0}/swift/account-server.conf.j2'.format(data['version']),
                    data=data):
                self.handlers['restart_swift-account-server'] = True

            if filer.template(
                    '/etc/swift/container-server.conf',
                    src='{0}/swift/container-server.conf.j2'.format(data['version']),
                    data=data):
                self.handlers['restart_swift-container-server'] = True

            if filer.template(
                    '/etc/swift/object-server.conf',
                    src='{0}/swift/object-server.conf.j2'.format(data['version']),
                    data=data):
                self.handlers['restart_swift-object-server'] = True

        if self.is_tag('data'):
            filer.mkdir('/mnt/swift/main')
            for ring in ['account', 'object', 'container']:
                port = data['{0}_port'.format(ring)]
                sudo('cd /etc/swift &&'
                     '[ -e {0}.builder ] || swift-ring-builder {0}.builder create 9 1 1 && '
                     '[ -e {0}.ring.gz ] || swift-ring-builder {0}.builder add z1-127.0.0.1:{1}/main 100 &&'  # noqa
                     '[ -e {0}.ring.gz ] || swift-ring-builder {0}.builder rebalance'.format(ring, port))  # noqa

        if self.is_tag('conf', 'service'):
            self.enable_services().start_services(pty=False)
            self.exec_handlers()

    def cmd(self, cmd):
        self.init()
        return utils.oscmd('swift {0}'.format(cmd))
