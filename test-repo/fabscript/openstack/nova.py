# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Nova


@task
@parallel
def setup():
    nova = Nova()
    nova.setup()

    return {'status': 1}
