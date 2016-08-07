# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Manila


@task
@parallel
def setup():
    manila = Manila()
    manila.setup()

    return {'status': 1}
