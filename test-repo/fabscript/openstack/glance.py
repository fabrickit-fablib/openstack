# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Glance


@task
@parallel
def setup():
    glance = Glance()
    glance.setup()

    return {'status': 1}
