# coding: utf-8

from fabkit import sudo


def oscmd(cmd):
    return sudo("source /root/openstackrcv3; {0}".format(cmd))
