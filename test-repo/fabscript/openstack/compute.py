# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Nova
from fablib.openstack import Neutron


@task
@parallel
def setup():
    nova = Nova('compute')
    nova.setup()

    neutron = Neutron('compute')
    neutron.setup()

    return {'status': 1}
