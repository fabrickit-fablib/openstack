# coding: utf-8

from fabkit import task, parallel, Service, Package


@task
@parallel
def setup():
    Package('memcached').install()
    Service('memcached').start().enable()

    return {'status': 1}
