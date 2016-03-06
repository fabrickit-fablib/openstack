# coding: utf-8

from fabkit import task, parallel
from fablib.gluster import Gluster


@task
@parallel
def setup():
    gluster = Gluster()
    gluster.setup()


@task
def setup1_peer():
    gluster = Gluster()
    gluster.setup_peer()


@task
def setup2_volume():
    gluster = Gluster()
    gluster.setup_volume()
    gluster.mount_local()
