# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Test


@task
@parallel
def setup():
    test = Test()
    test.basic()

    return {'status': 0}
