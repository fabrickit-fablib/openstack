# coding: utf-8

import time
from fabkit import *  # noqa
from keystone import Keystone
from glance import Glance
from nova import Nova
from fablib.base import SimpleBase
import utils


class Test(SimpleBase):
    def __init__(self):
        self.data_key = 'test_openstack'
        self.data = {}

    def basic(self):
        data = self.init()

        if env.host != env.hosts[0]:
            return

        keystone = Keystone()
        keystone.create_user(data['user'], data['password'], [['admin', 'admin']], False)

        glance = Glance()
        image_id = glance.create_image(
            data['image']['name'],
            data['image']['src_url'],
        )

        net_id = utils.oscmd("neutron net-list | grep ' {0} ' | awk '{{print $2}}'".format(
            env.cluster['neutron']['test_net']))

        nova = Nova()
        nova.create_flavor('test-flavor', 62, 2, 1)

        test_stack = {
            'image_id': image_id,
            'net_id': net_id,
            'flavor': 'test-flavor',
        }

        filer.template('/tmp/stack-nova.yml', src='stack/stack-nova.yml', data=test_stack)
        filer.template('/tmp/autoscale.yml', src='stack/autoscale.yml', data=test_stack)

        with api.warn_only():
            result = utils.oscmd('heat stack-list | grep stack-nova')
            if result.return_code == 0:
                utils.oscmd('heat stack-delete -y stack-nova')
                time.sleep(3)
            utils.oscmd('heat stack-create -f /tmp/stack-nova.yml stack-nova')
