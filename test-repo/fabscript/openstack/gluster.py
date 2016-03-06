# coding: utf-8

from fabkit import task, parallel
from fablib.gluster import Gluster


@task
@parallel
def setup():
    gluster = Gluster()
    gluster.setup()
    return {'status': 1}


@task
def setup1_peer():
    gluster = Gluster()
    gluster.setup_peer()
    return {'status': 1}


@task
def setup2_volume():
    gluster = Gluster()
    gluster.setup_volume()
    gluster.mount_local()
    return {'status': 1}
