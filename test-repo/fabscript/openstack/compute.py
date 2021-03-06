# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Nova, Neutron


@task
@parallel
def setup(enable_services=['.*']):
    nova = Nova(enable_services)
    nova.setup()

    neutron = Neutron(enable_services)
    neutron.setup()

    return {'status': 1}
