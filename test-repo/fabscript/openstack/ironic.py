# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Ironic


@task
@parallel
def setup():
    ironic = Ironic()
    ironic.setup()

    return {'status': 1}
