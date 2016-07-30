# coding: utf-8

from fabkit import task
from fablib.openstack import Devstack


@task
def setup():
    devstack = Devstack()
    devstack.setup()
