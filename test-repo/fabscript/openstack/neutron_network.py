# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Neutron


@task
@parallel
def setup(enable_services=['.*']):
    neutron = Neutron(enable_services)
    neutron.setup()

    return {'status': 1}
