# coding:utf-8

from fabkit import *  # noqa
from fablib.base import SimpleBase
from fablib import git


class Devstack(SimpleBase):
    def setup(self):
        sudo('setenforce 0')
        Editor('/etc/selinux/config').s('SELINUX=enforcing', 'SELINUX=disable')

        Service('firewalld').stop().disable()

        git.setup()
        dest = git.sync('https://github.com/openstack-dev/devstack.git', dest='/tmp/devstack', branch='stable/liberty')
        print dest

        filer.template('/tmp/devstack/local.conf')
