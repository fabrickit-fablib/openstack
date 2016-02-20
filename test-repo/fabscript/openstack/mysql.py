# coding: utf-8

from fabkit import task, serial
from fablib.mysql import MySQL


@task
def setup():
    mysql = MySQL()
    mysql.setup()
    return {'status': 1}


@task
@serial
def setup_replication():
    mysql = MySQL()
    mysql.setup_replication()
    return {'status': 1}
