# coding: utf-8

from fabkit import task, parallel
from fablib.haproxy import Haproxy


@task
@parallel
def setup():
    haproxy = Haproxy()
    haproxy.setup()
    return {'status': 1}


@task
def setup1_pcs():
    haproxy = Haproxy()
    haproxy.setup_pcs()
    haproxy.setup_pacemaker()
    return {'status': 1}
