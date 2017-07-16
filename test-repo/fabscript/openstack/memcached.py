# coding: utf-8

from fabkit import task, parallel
from fablib.memcached import Memcached


@task
@parallel
def setup():
    memcached = Memcached()
    memcached.setup()

    return {'status': 1}
