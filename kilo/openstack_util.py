# coding: utf-8
from fabkit import run, api, Package, env, filer, sudo
from fablib.repository import yum
import re


def setup_common(python):
    yum.install_epel()
    python.setup()
    Package('mysql-devel').install()
    Package('mysql').install()
    python.install('mysql-python')

    # kiloからは各種クライアントは非推奨で、openstackclientを利用する
    python.install('python-openstackclient')
    if not filer.exists('/usr/bin/openstack'):
        sudo('ln -s {0}/bin/openstack /usr/bin/'.format(python.get_prefix()))


def get_mysql_connection(data):
    mysql = env.cluster['mysql']
    name = data['database']['connection_name']
    conn = mysql['databases'][name]
    user = mysql['users'][conn['user']]
    conn['password'] = user['password']
    conn['str'] = 'mysql://{0[user]}:{0[password]}@{0[host]}:{0[port]}/{0[dbname]}'.format(conn)
    return conn


def convert_sql(connection, sql):
    sql = 'mysql -u{0[user]} -p{0[password]} -h{0[host]} -P{0[port]} {0[dbname]} -e "{1}"'.format(
        connection, sql)
    return sql


def show_tables(connection):
    result = run(convert_sql(connection, 'show tables'))
    RE_NAME = re.compile('\| ([a-z_]+)')
    tables = RE_NAME.findall(result)

    return tables


def client_cmd(cmd):
    keystone = env.cluster['keystone']
    with api.shell_env(
        OS_USERNAME='admin',
        OS_PASSWORD=keystone['admin_password'],
        OS_TENANT_NAME='admin',
        OS_AUTH_URL=keystone['services']['keystone']['adminurl'],
    ):
        return run(cmd)


def dump_openstackrc(keystone_data):
    run('''cat << _EOT_ > ~/openstackrc
export OS_USERNAME=admin
export OS_PASSWORD={0}
export OS_TENANT_NAME=admin
export OS_AUTH_URL={1}
_EOT_'''.format(keystone_data['admin_password'], keystone_data['services']['keystone']['adminurl']))
