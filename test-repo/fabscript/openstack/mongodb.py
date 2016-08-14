# coding: utf-8

from fabkit import task
from fablib.mongodb import MongoDB


@task
def setup():
    mongodb = MongoDB()
    mongodb.setup()

    return {'status': 1}
