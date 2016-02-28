# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Neutron


@task
@parallel
def setup():
    neutron = Neutron()
    neutron.setup()

    return {'status': 1}
