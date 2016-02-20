# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Keystone


@task
@parallel
def setup():
    keystone = Keystone()
    keystone.setup()

    return {'status': 1}


@task
def restart():
    keystone = Keystone()
    keystone.restart_services()
