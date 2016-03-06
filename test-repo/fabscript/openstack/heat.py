# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Heat


@task
@parallel
def setup():
    heat = Heat()
    heat.setup()

    return {'status': 1}
