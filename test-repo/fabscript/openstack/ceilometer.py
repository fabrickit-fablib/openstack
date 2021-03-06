# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Ceilometer


@task
@parallel
def setup(enable_services=['.*']):
    ceilometer = Ceilometer(enable_services)
    ceilometer.setup()

    return {'status': 1}
