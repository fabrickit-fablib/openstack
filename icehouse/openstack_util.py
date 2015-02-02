# coding: utf-8
from fabkit import sudo, run, filer, api, Package
from fablib import python
import re


def convert_mysql_connection(data):
    conn = 'mysql://{0[user]}:{0[password]}@{0[host]}:{0[port]}/{0[dbname]}'.format(data)
    return conn


def setup_init():
    setup_epel()
    python.setup()
    Package('mysql-devel').install()
    Package('mysql').install()
    sudo('pip install mysql-python')


def setup_epel():
    Package('epel-release').install('http://dl.fedoraproject.org/pub/epel/7/x86_64/e/epel-release-7-2.noarch.rpm')  # noqa


def setup_install(package_name, git_url, tmp_dir):
    encoding = run('python -c "import sys; print sys.getdefaultencoding()"')
    if encoding == 'ascii':
        site_packages = run('python -c "from distutils.sysconfig import get_python_lib; print get_python_lib()"')  # noqa
        sitecustomize = site_packages + '/sitecustomize.py'
        sudo('''echo "import sys
sys.setdefaultencoding(\'utf-8\')" >> {0}'''.format(sitecustomize))

    if not filer.exists(tmp_dir):
        run('git clone {0} {1}'.format(git_url, tmp_dir))  # noqa

    sudo('pip install -r {0}/requirements.txt'.format(tmp_dir))

    if not pip_show(package_name):
        sudo('sh -c "cd {0} && python setup.py install"'.format(tmp_dir))


def pip_show(package_name):
    import re
    result = run('pip show {0}'.format(package_name))
    if result == '':
        return None

    RE_NAME = re.compile('Name: (.+)\r')
    RE_VERSION = re.compile('Version: (.+)\r')
    name = RE_NAME.findall(result)[0]
    version = RE_VERSION.findall(result)[0]
    return (name, version)


def convert_sql(data, sql):
    sql = 'mysql -u{0[user]} -p{0[password]} -h{0[host]} -P{0[port]} {0[dbname]} -e "{1}"'.format(
        data, sql)
    return sql


def show_tables(data):
    result = run(convert_sql(data, 'show tables'))
    RE_NAME = re.compile('\| ([a-z_]+)')
    tables = RE_NAME.findall(result)

    return tables


def client_cmd(cmd, keystone_data):
    with api.shell_env(
        OS_USERNAME='admin',
        OS_PASSWORD=keystone_data['admin_password'],
        OS_TENANT_NAME='admin',
        OS_AUTH_URL=keystone_data['services']['keystone']['adminurl'],
    ):
        return run(cmd)


def dump_openstackrc(keystone_data):
    run('''cat << _EOT_ > ~/openstackrc
export OS_USERNAME=admin
export OS_PASSWORD={0}
export OS_TENANT_NAME=admin
export OS_AUTH_URL={1}
_EOT_'''.format(keystone_data['admin_password'], keystone_data['services']['keystone']['adminurl']))
