# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Swift


@task
@parallel
def setup():
    swift = Swift()
    swift.setup()

    return {'status': 1}
