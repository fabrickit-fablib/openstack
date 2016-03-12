# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Cinder


@task
@parallel
def setup():
    cinder = Cinder()
    cinder.setup()

    return {'status': 1}
