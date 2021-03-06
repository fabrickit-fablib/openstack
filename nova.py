# coding: utf-8

import time
from fabkit import sudo, env, filer, api
from fablib.base import SimpleBase
import re
import utils


class Nova(SimpleBase):
    def __init__(self, enable_services=['.*']):
        self.data_key = 'nova'
        self.data = {
            'user': 'root',
            'sudoers_cmd': 'ALL',
            'debug': 'true',
            'verbose': 'true',
            'timeout_nbd': 1,
            'is_nova-api': False,
            'is_nova-compute': False,
            'is_master': False,
        }

        default_services = [
            'nova-api-uwsgi',
            'nova-metadata-api-uwsgi',
            'nova-placement-api-uwsgi',
            'nova-scheduler',
            'nova-conductor',
            'nova-consoleauth',
            'nova-novncproxy',
            'nova-compute',
        ]

        self.enable_nginx = False

        self.packages = {
            'CentOS Linux 7.*': [],
            'Ubuntu 16.*': [],
        }
        self.services = []
        for service in default_services:
            for enable_service in enable_services:
                if re.search(enable_service, service):
                    if service == 'nova-placement-api-uwsgi':
                        self.services.append('nginx')
                        self.enable_nginx = True

                    self.services.append(service)
                    break

        if 'nova-api' in self.services:
            self.data['is_nova-api'] = True

        if 'nova-api-uwsgi' in self.services:
            self.data['is_nova-api'] = True

        if 'nova-novncproxy' in self.services:
            self.packages['CentOS Linux 7.*'].append('novnc')
            self.packages['Ubuntu 16.*'].append('novnc')

        if 'nova-compute' in self.services:
            self.data['is_nova-compute'] = True

            self.services.extend([
                'virtlogd',
                'libvirtd',
                'messagebus',
                'nova-compute',
            ])

            self.packages['CentOS Linux 7.*'].extend([
                'vde2-2.3.2',
                'qemu-2.9.0',
                'libvirt-3.6.0',
                'libvirt-python-3.6.0',
                'sysfsutils',
                'dbus',
                'genisoimage',
            ])

            self.packages['Ubuntu 16.*'].extend([
                'qemu',
                'libvirt-bin',
                'python-libvirt',
                'sysfsutils',
                'dbus',
                'genisoimage',
            ])

    def init_before(self):
        self.version = env.cluster[self.data_key]['version']
        if self.version == 'master':
            self.packages['CentOS Linux 7.*'].extend([
                'nova-18.0.0.0b1',
            ])
            self.packages['Ubuntu 16.*'].extend([
                'nova-18.0.0.0b1',
            ])

        elif self.version == 'pike':
            self.packages['CentOS Linux 7.*'].extend([
                'nova-16.0.0',
            ])
            self.packages['Ubuntu 16.*'].extend([
                'nova=16.0.0',
            ])

    def init_after(self):
        self.data.update({
            'timeout_nbd': 1,
            'sudoers_cmd': '/usr/bin/nova-rootwrap /etc/nova/rootwrap.conf *',
            'lock_path': '/var/lock/subsys/nova',
            'my_ip': env.node['ip']['default_dev']['ip'],
            'vncserver_listen': env.node['ip']['default_dev']['ip'],
            'vncserver_proxyclient_address': env.node['ip']['default_dev']['ip'],
            'keystone': env.cluster['keystone'],
        })

        if env.host == env.hosts[0] and self.data['is_nova-api']:
            self.data['is_master'] = True
        else:
            self.data['is_master'] = False

    def setup(self):
        data = self.init()

        if self.is_tag('package'):
            self.install_packages()

            # for cinder
            if not filer.exists('/usr/bin/scsi_id'):
                sudo('ln -s /lib/udev/scsi_id /usr/bin/')

            # if not filer.exists('/usr/bin/privsep-helper'):
            #     sudo('ln -s /opt/nova/bin/privsep-helper /usr/bin/')

            # if not filer.exists('/usr/bin/nova-rootwrap'):
            #     sudo('ln -s /opt/nova/bin/nova-rootwrap /usr/bin/')

            filer.template('/usr/lib/systemd/system/nova-api-uwsgi.service')
            filer.template('/usr/lib/systemd/system/nova-metadata-api-uwsgi.service')
            filer.template('/usr/lib/systemd/system/nova-placement-api-uwsgi.service')
            sudo('systemctl daemon-reload')

        if self.is_tag('conf'):
            filer.template('/etc/sudoers.d/nova', data=data, src='sudoers')

            self.setup_api_conf()
            self.setup_metadata_api_conf()
            self.setup_placement_api_conf()

            if filer.template(
                    '/etc/nova/nova.conf',
                    src='{0}/nova/nova.conf'.format(data['version']),
                    data=data):
                self.handlers['restart_nova'] = True

            if self.data['is_nova-compute']:
                if filer.template(
                        '/etc/libvirt/qemu.conf',
                        data=data):
                    self.handlers['restart_libvirtd'] = True

        if self.is_tag('data') and env.host == env.hosts[0]:
            if data['is_master']:
                sudo('/opt/nova/bin/nova-manage db sync')
                sudo('/opt/nova/bin/nova-manage api_db sync')

                # cetup cell0
                sudo('/opt/nova/bin/nova-manage cell_v2 list_cells | grep cell0 || /opt/nova/bin/nova-manage cell_v2 map_cell0')
                sudo('/opt/nova/bin/nova-manage db sync')
                sudo('/opt/nova/bin/nova-manage cell_v2 list_cells | grep cell1 || /opt/nova/bin/nova-manage cell_v2 create_cell --name cell1')

        if self.is_tag('service'):
            self.enable_services().start_services(pty=False)
            self.exec_handlers()

        if self.is_tag('data') and env.host == env.hosts[0]:
            if data['is_master']:
                self.sync_flavors()

        return 0

    def setup_api_conf(self):
        data = self.data
        data.update({
            'httpd_port': data['api_port'],
            'uwsgi_socket': '/var/run/nova-api-uwsgi.sock',
        })

        if filer.template(
            '/etc/nova/nova-api-uwsgi.ini',
            data=data,
        ):
            self.handlers['restart_nova-api-uwsgi'] = True

        if self.enable_nginx:
            if filer.template(
                '/etc/nginx/conf.d/nova-api-uwsgi.conf',
                src='uwsgi-nginx.conf',
                data=data,
            ):
                self.handlers['restart_nginx'] = True

    def setup_metadata_api_conf(self):
        data = self.data
        data.update({
            'httpd_port': data['metadata_port'],
            'uwsgi_socket': '/var/run/nova-metadata-api-uwsgi.sock',
        })

        if filer.template(
            '/etc/nova/nova-metadata-api-uwsgi.ini',
            data=data,
        ):
            self.handlers['restart_nova-metadata-api-uwsgi'] = True

        if self.enable_nginx:
            if filer.template(
                '/etc/nginx/conf.d/nova-metadata-api-uwsgi.conf',
                src='uwsgi-nginx.conf',
                data=data,
            ):
                self.handlers['restart_nginx'] = True

    def setup_placement_api_conf(self):
        data = self.data
        data.update({
            'httpd_port': data['placement_port'],
            'uwsgi_socket': '/var/run/nova-placement-api-uwsgi.sock',
        })

        if filer.template(
            '/etc/nova/nova-placement-api-uwsgi.ini',
            data=data,
        ):
            self.handlers['restart_nova-placement-api-uwsgi'] = True

        if self.enable_nginx:
            if filer.template(
                '/etc/nginx/conf.d/nova-placement-api-uwsgi.conf',
                src='uwsgi-nginx.conf',
                data=data,
            ):
                self.handlers['restart_nginx'] = True

    def cmd(self, cmd):
        self.init()
        return utils.oscmd('openstack {0}'.format(cmd))

    def check(self):
        self.nova_api.status()
        self.nova_cert.status()
        self.nova_consoleauth.status()
        self.nova_scheduler.status()
        self.nova_conductor.status()
        self.nova_novncproxy.status()

    def enable_nova_services(self):
        return
        result = sudo("/opt/nova/bin/nova-manage service list 2>/dev/null | grep disabled | awk '{print $1,$2}'")
        services = result.split('\r\n')
        services = map(lambda s: s.split(' '), services)
        for service in services:
            sudo("/opt/nova/bin/nova-manage service enable --service {0} --host {1}".format(
                service[0], service[1]))

    def sync_flavors(self):
        data = self.init()
        with api.warn_only():
            ttl = 3
            while True:
                result = self.cmd("flavor list")
                if result.return_code == 0:
                    break
                time.sleep(10)
                ttl -= 1
                if ttl == 0:
                    raise Exception("nova is not available.")

        result = self.cmd("flavor list 2>/dev/null | grep '| ' | grep -v '| ID' | awk '{print $4}'")
        flavor_list = result.split('\r\n')
        sub_set = set(flavor_list) - set(data['flavors'].keys())
        for flavor_name in sub_set:
            if len(flavor_name) == 0:
                continue
            self.cmd("flavor delete {0}".format(flavor_name))

        for flavor_name, flavor in data['flavors'].items():
            if flavor_name not in flavor_list:
                self.cmd("flavor create {0} {1}".format(flavor['options'], flavor_name))
