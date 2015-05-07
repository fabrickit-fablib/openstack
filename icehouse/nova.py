# coding: utf-8

from fabkit import sudo, env, user, Package, filer
from fablib import python
import openstack_util


class Nova():
    def __init__(self):
        self.data_key = 'nova'
        self.data = {
            'user': 'nova',
            'novncproxy_base_url': 'http://127.0.0.1:6080/vnc_auto.html',
        }

        self.services = [
            'openstack-nova-api'
            'openstack-nova-cert'
            'openstack-nova-consoleauth'
            'openstack-nova-scheduler'
            'openstack-nova-conductor'
            'openstack-nova-novncproxy'
        ]

        # self.services = [
        #     'libvirtd',
        #     'messagebus',
        #     'openstack-nova-compute',
        # ]

    def init_data(self):
        self.connection = openstack_util.get_mysql_connection(self.data)
        self.data.update({
            'keystone': env.cluster['keystone'],
            'database': {
                'connection': self.connection['str']
            },
        })

    def setup(self):
        is_updated = self.install()

        return

        self.db_sync()

        self.enable_services().start_services(pty=False)

        if is_updated:
            self.restart_services(pty=False)

        self.cmd('image-list')

        return 0

    def setup_compute(self):
        is_updated = self.install()
        is_updated = self.install_compute() or is_updated
        self.libvirtd.enable().start(pty=False)
        self.messagebus.enable().start(pty=False)
        self.nova_compute.enable().start(pty=False)
        if is_updated:
            self.libvirtd.restart(pty=False)
            self.messagebus.restart(pty=False)
            self.nova_compute.restart(pty=False)

        return 0

    def cmd(self, cmd):
        return openstack_util.client_cmd('nova {0}'.format(cmd), self.keystone_data)

    def install(self):
        openstack_util.setup_common()

        user.add(self.data['user'])

        sudo('pip install python-novaclient')

        pkg = python.install_from_git(
            'nova',
            'https://github.com/openstack/nova.git -b stable/icehouse')

        filer.mkdir(self.data['lock_path'], owner='nova:nova')

        if not filer.exists('/etc/nova'):
            sudo('cp -r {0}/etc/nova/ /etc/nova/'.format(pkg['git_dir']))

        is_updated = filer.template(
            '/etc/nova/nova.conf',
            data=self.data,
        )

        filer.mkdir('/var/log/nova', owner='nova:nova')
        option = '--log-dir /var/log/nova/'

        is_updated = filer.template('/etc/init.d/openstack-nova-api', '755',
                                    data={
                                        'prog': 'nova-api',
                                        'option': option,
                                        'config': '/etc/nova/nova.conf',
                                        'user': self.data['user'],
                                    },
                                    src_target='initscript') or is_updated

        is_updated = filer.template('/etc/init.d/openstack-nova-cert', '755',
                                    data={
                                        'prog': 'nova-cert',
                                        'option': option,
                                        'config': '/etc/nova/nova.conf',
                                        'user': self.data['user'],
                                    },
                                    src_target='initscript') or is_updated

        is_updated = filer.template('/etc/init.d/openstack-nova-consoleauth', '755',
                                    data={
                                        'prog': 'nova-consoleauth',
                                        'option': option,
                                        'config': '/etc/nova/nova.conf',
                                        'user': self.data['user'],
                                    },
                                    src_target='initscript') or is_updated

        is_updated = filer.template('/etc/init.d/openstack-nova-scheduler', '755',
                                    data={
                                        'prog': 'nova-scheduler',
                                        'config': '/etc/nova/nova.conf',
                                        'user': self.data['user'],
                                    },
                                    src_target='initscript') or is_updated

        is_updated = filer.template('/etc/init.d/openstack-nova-conductor', '755',
                                    data={
                                        'prog': 'nova-conductor',
                                        'option': option,
                                        'config': '/etc/nova/nova.conf',
                                        'user': self.data['user'],
                                    },
                                    src_target='initscript') or is_updated

        is_updated = filer.template('/etc/init.d/openstack-nova-novncproxy', '755',
                                    data={
                                        'prog': 'nova-novncproxy',
                                        'option': option,
                                        'config': '/etc/nova/nova.conf',
                                        'user': self.data['user'],
                                    },
                                    src_target='initscript') or is_updated

        is_updated = filer.template('/etc/init.d/openstack-nova-compute', '755',
                                    data={
                                        'prog': 'nova-compute',
                                        'option': option,
                                        'config': '/etc/nova/nova.conf',
                                        'user': self.data['user'],
                                    },
                                    src_target='initscript') or is_updated

        return is_updated

    def check(self):
        self.nova_api.status()
        self.nova_cert.status()
        self.nova_consoleauth.status()
        self.nova_scheduler.status()
        self.nova_conductor.status()
        self.nova_novncproxy.status()

    def install_compute(self):
        Package('libvirt').install()
        Package('python-virtinst').install()
        Package('qemu-kvm').install()
        Package('dbus').install()

    def db_sync(self):
        if not openstack_util.show_tables(self.data['database']['data']) == sorted([
            'agent_builds',
            'aggregate_hosts',
            'aggregate_metadata',
            'aggregates',
            'block_device_mapping',
            'bw_usage_cache',
            'cells',
            'certificates',
            'compute_nodes',
            'console_pools',
            'consoles',
            'dns_domains',
            'fixed_ips',
            'floating_ips',
            'instance_actions',
            'instance_actions_events',
            'instance_faults',
            'instance_group_member',
            'instance_group_metadata',
            'instance_group_policy',
            'instance_groups',
            'instance_id_mappings',
            'instance_info_caches',
            'instance_metadata',
            'instance_system_metadata',
            'instance_type_extra_specs',
            'instance_type_projects',
            'instance_types',
            'instances',
            'iscsi_targets',
            'key_pairs',
            'migrate_version',
            'migrations',
            'networks',
            'pci_devices',
            'project_user_quotas',
            'provider_fw_rules',
            'quota_classes',
            'quota_usages',
            'quotas',
            'reservations',
            's',
            'security_group_default_rules',
            'security_group_instance_association',
            'security_group_rules',
            'security_groups',
            'services',
            'shadow_agent_builds',
            'shadow_aggregate_hosts',
            'shadow_aggregate_metadata',
            'shadow_aggregates',
            'shadow_block_device_mapping',
            'shadow_bw_usage_cache',
            'shadow_cells',
            'shadow_certificates',
            'shadow_compute_nodes',
            'shadow_console_pools',
            'shadow_consoles',
            'shadow_dns_domains',
            'shadow_fixed_ips',
            'shadow_floating_ips',
            'shadow_instance_actions',
            'shadow_instance_actions_events',
            'shadow_instance_faults',
            'shadow_instance_group_member',
            'shadow_instance_group_metadata',
            'shadow_instance_group_policy',
            'shadow_instance_groups',
            'shadow_instance_id_mappings',
            'shadow_instance_info_caches',
            'shadow_instance_metadata',
            'shadow_instance_system_metadata',
            'shadow_instance_type_extra_specs',
            'shadow_instance_type_projects',
            'shadow_instance_types',
            'shadow_instances',
            'shadow_iscsi_targets',
            'shadow_key_pairs',
            'shadow_migrate_version',
            'shadow_migrations',
            'shadow_networks',
            'shadow_pci_devices',
            'shadow_project_user_quotas',
            'shadow_provider_fw_rules',
            'shadow_quota_classes',
            'shadow_quota_usages',
            'shadow_quotas',
            'shadow_reservations',
            'shadow_s',
            'shadow_security_group_default_rules',
            'shadow_security_group_instance_association',
            'shadow_security_group_rules',
            'shadow_security_groups',
            'shadow_services',
            'shadow_snapshot_id_mappings',
            'shadow_snapshots',
            'shadow_task_log',
            'shadow_virtual_interfaces',
            'shadow_volume_id_mappings',
            'shadow_volume_usage_cache',
            'shadow_volumes',
            'snapshot_id_mappings',
            'snapshots',
            'task_log',
            'virtual_interfaces',
            'volume_id_mappings',
            'volume_usage_cache',
            'volumes'
        ]):
            sudo('nova-manage db sync')
