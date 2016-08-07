# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Designate


@task
@parallel
def setup():
    designate = Designate()
    designate.setup()

    return {'status': 1}
