# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Horizon


@task
@parallel
def setup():
    horizon = Horizon()
    horizon.setup()

    return {'status': 1}
