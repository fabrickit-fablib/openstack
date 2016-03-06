# coding: utf-8

from fabkit import filer, env
from keystone import Keystone
from glance import Glance
from nova import Nova
from fablib.base import SimpleBase
import utils


class Test(SimpleBase):
    def basic(self):
        if env.host != env.hosts[0]:
            return

        keystone = Keystone()
        keystone.create_user('testuser', 'testuser', [['admin', 'admin']])

        glance = Glance()
        image_id = glance.create_image(
            'cirros-0.3.3-x86_64',
            'http://download.cirros-cloud.net/0.3.3/cirros-0.3.3-x86_64-disk.img',
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

        print test_stack

        filer.template('/tmp/stack-nova.yml', src='stack/stack-nova.yml', data=test_stack)

        utils.oscmd('heat stack-create -f /tmp/stack-nova.yml stack-nova')
