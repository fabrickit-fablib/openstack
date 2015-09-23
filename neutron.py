# coding: utf-8

import socket
import struct
from fabkit import sudo, env, filer, run, Service, api
from fablib.python import Python
from tools import Tools
from fablib.base import SimpleBase

MODE_CONTROLLER = 'controller'
MODE_COMPUTE = 'compute'
MODE_NETWORK = 'network'


class Neutron(SimpleBase):
    def __init__(self, mode=MODE_CONTROLLER):
        self.mode = mode
        self.data_key = 'neutron'
        self.data = {
            'sudoers_cmd': 'ALL',
            'debug': True,
            'verbose': True,
            'user': 'neutron',
            'auth_strategy': 'keystone',
            'rpc_backend': 'neutron.openstack.common.rpc.impl_kombu',
            'core_plugin': 'ml2',
        }
        self.packages = ['openvswitch']

    def init_before(self):
        self.package = env['cluster']['os_package_map']['neutron']
        self.prefix = self.package.get('prefix', '/opt/neutron')
        self.python = Python(self.prefix)
        self.tools = Tools(self.python)
        neutron = env.cluster['neutron']

        self.services = []
        if self.mode == MODE_CONTROLLER:
            self.services = ['neutron-server']
        elif self.mode == MODE_COMPUTE:
            if neutron.get('linuxbridge', {}).get('enable'):
                self.services.append('neutron-linuxbridge-agent')
            if neutron.get('ovs', {}).get('enable'):
                self.services.append('neutron-openvswitch-agent')
        elif self.mode == MODE_NETWORK:
            if neutron.get('ovs', {}).get('enable'):
                self.services.append('neutron-openvswitch-agent')
            if neutron.get('l3', {}).get('enable'):
                self.services.append('neutron-l3-agent')
            if neutron.get('dhcp', {}).get('enable'):
                self.services.append('neutron-dhcp-agent')
            if neutron.get('metadata', {}).get('enable'):
                self.services.append('neutron-metadata-agent')

    def init_after(self):
        self.data.update({
            'keystone': env.cluster['keystone'],
            'my_ip': env.node['ip']['default_dev']['ip'],
        })

    def setup(self):
        data = self.init()

        if self.is_tag('package'):
            self.tools.setup()
            self.install_packages()
            sudo('modprobe tun')

            if not filer.exists('/usr/bin/neutron'):
                sudo('ln -s {0}/bin/neutron /usr/bin/'.format(self.prefix))

            self.python.install_from_git(**self.package)

        if self.is_tag('network') and self.mode == MODE_NETWORK:
            Service('openvswitch').start().enable()
            sudo('ovs-vsctl br-exists {0} || ovs-vsctl add-br {0}'.format(data['ovs']['integration_bridge']))
            filer.template(
                '/etc/sysconfig/network-scripts/ifcfg-{0}'.format(data['ovs']['integration_bridge']),
                src='network/ovs-ifcfg-br.j2',
                data=data)


            for mapping in data['ovs']['physical_interface_mappings']:
                pair = mapping.split(':')
                ovs_interface = pair[0]
                physical_interface = pair[1]
                sudo('ovs-vsctl br-exists {0} || ovs-vsctl add-br {0}'.format(ovs_interface))
                print env.node['ip']['default_dev']
                if physical_interface == 'default':
                    data['ovs_interface'] = ovs_interface
                    backup = '/etc/sysconfig/network-scripts/default-ifcfg'
                    if filer.exists(backup):
                        default = run('cat {0}'.format(backup))
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
                            backup))
                        data['default_dev'] = env.node['ip']['default_dev']
                        data['default_dev']['gateway'] = env.node['ip']['default']['ip']
                    data['default_dev']['netmask'] = self.cidr(data['default_dev']['subnet'].split('/')[1])

                    filer.template(
                        '/etc/sysconfig/network-scripts/ifcfg-{0}'.format(data['default_dev']['dev']),
                        src='network/ovs-ifcfg-flat.j2',
                        data=data)

                    filer.template(
                        '/etc/sysconfig/network-scripts/ifcfg-{0}'.format(ovs_interface),
                        src='network/ovs-ifcfg-br-flat.j2',
                        data=data)

                    result = sudo('ovs-vsctl list-ports {0}'.format(ovs_interface))
                    if result.find(data['default_dev']['dev']) > -1:
                        with api.warn_only():
                            api.reboot()

        if self.is_tag('conf'):
            is_updated = filer.template(
                '/etc/sudoers.d/neutron',
                data=data,
                src='sudoers.j2',
            )

            is_updated = filer.template(
                '/etc/neutron/neutron.conf',
                src='{0}/neutron.conf.j2'.format(data['version']),
                data=data,
            )

            is_updated = filer.template(
                '/etc/neutron/plugins/ml2/ml2_conf.ini',
                src='{0}/ml2_conf.ini.j2'.format(data['version']),
                data=data,
            ) or is_updated

            is_updated = filer.template(
                '/etc/neutron/plugins/linuxbridge/linuxbridge_conf.ini',
                src='{0}/linuxbridge_conf.ini.j2'.format(data['version']),
                data=data,
            ) or is_updated

            is_updated = filer.template(
                '/etc/neutron/plugins/openvswitch/ovs_neutron_plugin.ini',
                src='{0}/ovs_neutron_plugin.ini.j2'.format(data['version']),
                data=data,
            ) or is_updated

            is_updated = filer.template(
                '/etc/neutron/l3_agent.ini',
                src='{0}/l3_agent.ini.j2'.format(data['version']),
                data=data,
            ) or is_updated

            is_updated = filer.template(
                '/etc/neutron/dhcp_agent.ini',
                src='{0}/dhcp_agent.ini.j2'.format(data['version']),
                data=data,
            ) or is_updated

            is_updated = filer.template(
                '/etc/neutron/metadata_agent.ini',
                src='{0}/metadata_agent.ini.j2'.format(data['version']),
                data=data,
            ) or is_updated

        if self.is_tag('data'):
            option = '--config-file /etc/neutron/neutron.conf' \
                + ' --config-file /etc/neutron/plugins/ml2/ml2_conf.ini' \
                + ' --config-file /etc/neutron/plugins/linuxbridge/linuxbridge_conf.ini'

            run('{0}/bin/neutron-db-manage {1} upgrade head'.format(self.prefix, option))

        if self.is_tag('service'):
            self.enable_services().start_services(pty=False)

            if is_updated:
                self.restart_services(pty=False)

        if self.is_tag('data'):
            if self.mode == MODE_CONTROLLER:
                self.create_nets()

        return 0

    def cmd(self, cmd):
        return self.tools.cmd('neutron {0}'.format(cmd))

    def create_nets(self):
        data = self.init()

        result = self.cmd("net-list 2>/dev/null | grep '| ' | grep -v '| id' | awk '{print $4}'")
        net_list = result.split('\r\n')
        result = self.cmd("subnet-list 2>/dev/null | grep '| ' | grep -v '| id' | awk '{print $4}'")
        subnet_list = result.split('\r\n')

        for network in data['networks']:
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

    def cidr(self, prefix):
        prefix = int(prefix)
        return socket.inet_ntoa(struct.pack(">I", (0xffffffff << (32 - prefix)) & 0xffffffff))
