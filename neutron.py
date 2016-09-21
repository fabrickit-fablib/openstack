# coding: utf-8

import re
import socket
import struct
import time
from fabkit import sudo, env, filer, run, Service, api
from fablib.python import Python
from fablib.base import SimpleBase
import utils


class Neutron(SimpleBase):
    def __init__(self, enable_services=['.*']):
        self.data_key = 'neutron'
        self.data = {
            'sudoers_cmd': 'ALL',
            'debug': True,
            'verbose': True,
            'user': 'neutron',
            'auth_strategy': 'keystone',
            'core_plugin': 'ml2',
            'is_neutron-server': False,
            'is_master': False,
        }
        self.packages = ['openvswitch', 'haproxy', 'ebtables']

        default_services = [
            'neutron-server',
            'neutron-linuxbridge-agent',
            'neutron-openvswitch-agent',
            'neutron-dhcp-agent',
            'neutron-l3-agent',
            'neutron-metadata-agent',
            'neutron-lbaasv2-agent',
        ]

        self.services = []
        for service in default_services:
            for enable_service in enable_services:
                if re.search(enable_service, service):
                    self.services.append(service)
                    break

        if 'neutron-server' in self.services:
            self.data['is_neutron-server'] = True

    def init_before(self):
        self.package = env['cluster']['os_package_map']['neutron']
        self.prefix = self.package.get('prefix', '/opt/neutron')
        self.python = Python(self.prefix)

    def init_after(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
            'my_ip': env.node['ip']['default_dev']['ip'],
        })

        if env.host == env.hosts[0] and self.data['is_neutron-server']:
            self.data['is_master'] = True
        else:
            self.data['is_master'] = False

    def setup(self):
        data = self.init()

        if self.is_tag('package'):
            self.python.setup()
            self.install_packages()
            self.python.setup_package(**self.package)
            sudo('modprobe tun')  # for vhost_net

            self.setup_network_bridge()

        if self.is_tag('conf'):
            filer.template(
                '/etc/sudoers.d/neutron',
                data=data,
                src='sudoers.j2',
            )

            if filer.template(
                '/etc/neutron/neutron.conf',
                src='{0}/neutron.conf.j2'.format(data['version']),
                data=data,
            ):
                self.handlers['restart_neutron-*'] = True

            if filer.template(
                '/etc/neutron/plugins/ml2/ml2_conf.ini',
                src='{0}/ml2_conf.ini.j2'.format(data['version']),
                data=data,
            ):
                self.handlers['restart_neutron-*'] = True

            if self.data['version'] == 'kilo':
                linuxbridge_conf = '/etc/neutron/plugins/linuxbridge/linuxbridge_conf.ini'
            elif self.data['version'] in ['liberty', 'mitaka', 'master']:
                linuxbridge_conf = '/etc/neutron/plugins/ml2/linuxbridge_agent.ini'

            if filer.template(
                linuxbridge_conf,
                src='{0}/linuxbridge_conf.ini.j2'.format(data['version']),
                data=data,
            ):
                self.handlers['restart_neutron-*'] = True

            if self.data['version'] == 'kilo':
                ovs_conf = '/etc/neutron/plugins/openvswitch/ovs_neutron_plugin.ini'
            elif self.data['version'] in ['liberty', 'mitaka', 'master']:
                ovs_conf = '/etc/neutron/plugins/ml2/openvswitch_agent.ini'

            if 'openvswitch' in self.data['ml2']['mechanism_drivers']:
                if filer.template(
                    ovs_conf,
                    src='{0}/ovs_neutron_plugin.ini.j2'.format(data['version']),
                    data=data,
                ):
                    self.handlers['restart_neutron-*'] = True

                if filer.template(
                    '/etc/neutron/l3_agent.ini',
                    src='{0}/l3_agent.ini.j2'.format(data['version']),
                    data=data,
                ):
                    self.handlers['restart_neutron-*'] = True
            else:
                sudo('echo '' > {0}'.format(ovs_conf))

            if filer.template(
                '/etc/neutron/dhcp_agent.ini',
                src='{0}/dhcp_agent.ini.j2'.format(data['version']),
                data=data,
            ):
                self.handlers['restart_neutron-*'] = True

            if filer.template(
                '/etc/neutron/metadata_agent.ini',
                src='{0}/metadata_agent.ini.j2'.format(data['version']),
                data=data,
            ):
                self.handlers['restart_neutron-*'] = True

            # lbaas
            if filer.template(
                '/etc/neutron/services_lbaas.conf',
                src='{0}/services_lbaas.conf.j2'.format(data['version']),
                data=data,
            ):
                self.handlers['restart_neutron-*'] = True

            if filer.template(
                '/etc/neutron/neutron_lbaas.conf',
                src='{0}/neutron_lbaas.conf.j2'.format(data['version']),
                data=data,
            ):
                self.handlers['restart_neutron-*'] = True

            if filer.template(
                '/etc/neutron/lbaas_agent.ini',
                src='{0}/lbaas_agent.ini.j2'.format(data['version']),
                data=data,
            ):
                self.handlers['restart_neutron-*'] = True

        if self.is_tag('data') and env.host == env.hosts[0]:
            if data['is_master']:
                option = '--config-file /etc/neutron/neutron.conf'
                run('{0}/bin/neutron-db-manage {1} upgrade head'.format(self.prefix, option))
                run('{0}/bin/neutron-db-manage {1} --service lbaas upgrade head'.format(
                    self.prefix, option))

        if self.is_tag('service'):
            self.enable_services().start_services(pty=False)
            self.exec_handlers()

        if self.is_tag('data') and env.host == env.hosts[0]:
            if data['is_master']:
                time.sleep(5)
                self.create_nets()
                self.create_routers()

        return 0

    def cmd(self, cmd):
        return utils.oscmd('neutron {0}'.format(cmd))

    def create_nets(self):
        data = self.init()

        result = self.cmd("net-list 2>/dev/null | grep '| ' | grep -v '| id' | awk '{print $4}'")
        net_list = result.split('\r\n')
        result = self.cmd("subnet-list 2>/dev/null | grep '| ' | grep -v '| id' | awk '{print $4}'")
        subnet_list = result.split('\r\n')

        for network in data.get('networks'):
            if network['name'] not in net_list:
                tmp_options = map(lambda opt: '--' + opt, network.get('options', []))
                options = ' '.join(tmp_options)
                self.cmd('net-create {0} {1}'.format(options, network['name']))

            for subnet in network['subnets']:
                if subnet['name'] not in subnet_list:
                    tmp_options = map(lambda opt: '--' + opt, subnet.get('options', []))
                    options = ' '.join(tmp_options)
                    self.cmd('subnet-create {0} {1} --name {2} {3}'.format(
                        network['name'], subnet['cidr'], subnet['name'], options))

    def create_routers(self):
        data = self.init()
        with api.warn_only():
            for router in data.get('routers', []):
                result = self.cmd('router-show {0}'.format(router['name']))
                if result.return_code == 0:
                    continue

                self.cmd('router-create {0}'.format(router['name']))
                self.cmd('router-gateway-set {0} {1}'.format(router['name'], router['gateway']))
                for interface in router['interfaces']:
                    self.cmd('router-interface-add {0} {1}'.format(router['name'], interface))

    def setup_network_bridge(self):
        data = self.init()

        if 'linuxbridge' in data['ml2']['mechanism_drivers']:
            sudo('modprobe bridge')

        elif 'openvswitch' in data['ml2']['mechanism_drivers']:
            sudo('modprobe -r bridge')
            Service('openvswitch').start().enable()

            sudo('ovs-vsctl br-exists {0} || ovs-vsctl add-br {0}'.format(
                data['ovs']['integration_bridge']))

            filer.template(
                '/etc/sysconfig/network-scripts/ifcfg-{0}'.format(
                    data['ovs']['integration_bridge']),
                src='network/ovs-ifcfg-br.j2',
                data=data)

            for mapping in data['ovs']['bridge_mappings']:
                pair = mapping.split(':')
                ovs_interface = pair[1]
                sudo('ovs-vsctl br-exists {0} || ovs-vsctl add-br {0}'.format(ovs_interface))

            for mapping in data['ovs']['physical_interface_mappings']:
                pair = mapping.split(':')
                ovs_interface = pair[0]
                physical_interface = pair[1]

                backup_default_dev_file = '/etc/sysconfig/network-scripts/bk-ifcfg-defualt'
                if filer.exists(backup_default_dev_file):
                    default = run('cat {0}'.format(backup_default_dev_file))
                    dev, ip, subnet, gateway = default.split(':')
                    data['default_dev'] = {
                        'dev': dev,
                        'ip': ip,
                        'subnet': subnet,
                        'gateway': gateway,
                    }
                else:
                    sudo("echo '{0[dev]}:{0[ip]}:{0[subnet]}:{1}' > {2}".format(
                        env.node['ip']['default_dev'],
                        env.node['ip']['default']['ip'],
                        backup_default_dev_file))
                    data['default_dev'] = env.node['ip']['default_dev']
                    data['default_dev']['gateway'] = env.node['ip']['default']['ip']

                data['default_dev']['netmask'] = self.cidr(
                    data['default_dev']['subnet'].split('/')[1])

                if physical_interface == data['default_dev']['dev']:
                    # create backup for default interface

                    data['ovs_interface'] = ovs_interface

                    filer.template(
                        '/etc/sysconfig/network-scripts/ifcfg-{0}'.format(physical_interface),
                        src='network/ovs-ifcfg-flat.j2',
                        data=data)

                    filer.template(
                        '/etc/sysconfig/network-scripts/ifcfg-{0}'.format(ovs_interface),
                        src='network/ovs-ifcfg-br-flat.j2',
                        data=data)

                    result = sudo('ovs-vsctl list-ports {0}'.format(ovs_interface))
                    if result.find(data['default_dev']['dev']) == -1:
                        with api.warn_only():
                            api.reboot(180)

    def cidr(self, prefix):
        prefix = int(prefix)
        return socket.inet_ntoa(struct.pack(">I", (0xffffffff << (32 - prefix)) & 0xffffffff))
