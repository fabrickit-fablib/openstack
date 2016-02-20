# coding: utf-8

from fabkit import task, parallel
from fablib.openstack import Bootstrap


@task
@parallel
def setup():
    bootstrap = Bootstrap()
    bootstrap.setup()
    bootstrap.dump_openstackrc()

    return {'status': 1}
