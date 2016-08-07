# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Trove


@task
@parallel
def setup():
    trove = Trove()
    trove.setup()

    return {'status': 1}
