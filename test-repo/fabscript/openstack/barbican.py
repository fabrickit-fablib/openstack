# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Barbican


@task
@parallel
def setup():
    barbican = Barbican()
    barbican.setup()

    return {'status': 1}
