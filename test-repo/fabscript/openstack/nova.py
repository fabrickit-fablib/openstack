# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Nova


@task
@parallel
def setup(enable_services=['.*']):
    nova = Nova(enable_services)
    nova.setup()

    return {'status': 1}
