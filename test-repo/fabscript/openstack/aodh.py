# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Aodh


@task
@parallel
def setup(enable_services=['.*']):
    aodh = Aodh(enable_services)
    aodh.setup()

    return {'status': 1}
