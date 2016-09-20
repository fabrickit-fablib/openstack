# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Rally


@task
@parallel
def setup():
    rally = Rally()
    rally.setup()

    return {'status': 1}
