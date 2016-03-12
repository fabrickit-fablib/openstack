# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Ceilometer


@task
@parallel
def setup():
    ceilometer = Ceilometer()
    ceilometer.setup()

    return {'status': 1}
