# coding: utf-8

from fabkit import task
from fablib.rabbitmq import RabbitMQ


@task
def setup():
    rabbitmq = RabbitMQ()
    rabbitmq.setup()
    rabbitmq.setup_cluster()

    return {'status': 1}
