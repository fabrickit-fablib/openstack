# coding: utf-8

from fabkit import run, api, env


def oscmd(cmd):
    keystone = env.cluster['keystone']
    with api.shell_env(
        OS_USERNAME='admin',
        OS_PASSWORD=keystone['admin_password'],
        OS_TENANT_NAME='admin',
        OS_AUTH_URL=keystone['services']['keystone']['adminurl'],
    ):
        return run(cmd)
