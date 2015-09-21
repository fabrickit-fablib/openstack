# coding: utf-8

from fabkit import sudo, env, filer, run
from fablib.python import Python
from tools import Tools
from fablib.base import SimpleBase

MODE_CONTROLLER = 1
MODE_COMPUTE = 2


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

    def init_before(self):
        self.package = env['cluster']['os_package_map']['neutron']
        self.prefix = self.package.get('prefix', '/opt/neutron')
        self.python = Python(self.prefix)
        self.tools = Tools(self.python)

        if self.mode == MODE_CONTROLLER:
            self.services = ['neutron-server']
        elif self.mode == MODE_COMPUTE:
            neutron = env.cluster['neutron']
            self.services = []
            if neutron.get('linuxbridge', {}).get('enable'):
                self.services.append('neutron-linuxbridge-agent')
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

            if not filer.exists('/usr/bin/neutron'):
                sudo('ln -s {0}/bin/neutron /usr/bin/'.format(self.prefix))

            self.python.install_from_git(**self.package)

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

        for network_name, network in data['networks'].items():
            if network_name not in net_list:
                tmp_options = map(lambda opt: '--' + opt, network['options'])
                options = ' '.join(tmp_options)
                self.cmd('net-create {0} {1}'.format(options, network_name))

            for subnet_name, subnet in network['subnets'].items():
                if subnet_name not in subnet_list:
                    tmp_options = map(lambda opt: '--' + opt, subnet['options'])
                    options = ' '.join(tmp_options)
                    self.cmd('subnet-create {0} {1} --name {2} {3}'.format(
                        network_name, subnet['cidr'], subnet_name, options))
