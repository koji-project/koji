import mock
import unittest

import koji
import koji.policy
import kojihub
import kojixmlrpc


class OurException(Exception):
    pass


class BadTest(koji.policy.BaseSimpleTest):
    name = 'badtest'
    def run(self, data):
        raise OurException('this is a bad test')


class FakePlugin(object):
    pass


class TestCheckVolumePolicy(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        self.lookup_name = mock.patch('kojihub.lookup_name').start()

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('kojixmlrpc.kojihub', new=kojihub, create=True)
    def load_policy(self, policy):
        '''policy is the policy dict with text values'''
        plugin = FakePlugin()
        plugin.BadTest = BadTest
        policy = kojixmlrpc.get_policy(
                {'policy': policy, 'Plugins': 'fake_plugin'},
                plugins={'fake_plugin': plugin})
        self.context.policy = policy

    def test_volume_policy_bad(self):
        self.load_policy({'volume': 'bool no_such_field :: testvol'})

        ret = kojihub.check_volume_policy({})
        self.assertEqual(ret, None)

        with self.assertRaises(KeyError):
            kojihub.check_volume_policy({}, strict=True)

        self.lookup_name.assert_not_called()

    def test_volume_policy_badtest(self):
        # the badtest handler (defined above) always raises an error
        self.load_policy({'volume': 'badtest :: testvol'})

        ret = kojihub.check_volume_policy({})
        self.assertEqual(ret, None)

        with self.assertRaises(OurException):
            kojihub.check_volume_policy({}, strict=True)

        self.lookup_name.assert_not_called()

    def test_volume_policy_nomatch(self):
        self.load_policy({'volume': 'bool foo :: testvol'})
        data = {'foo': False}

        ret = kojihub.check_volume_policy(data)
        self.assertEqual(ret, None)

        with self.assertRaises(koji.GenericError):
            kojihub.check_volume_policy(data, strict=True)

        self.lookup_name.assert_not_called()

    def test_volume_policy_badvolume(self):
        self.load_policy({'volume': 'bool foo :: testvol'})
        data = {'foo': True}
        self.lookup_name.return_value = None

        ret = kojihub.check_volume_policy(data)
        self.assertEqual(ret, None)
        self.lookup_name.assert_called_once_with('volume', 'testvol')

        # and again with strict on
        self.lookup_name.reset_mock()
        with self.assertRaises(koji.GenericError):
            kojihub.check_volume_policy(data, strict=True)
        self.lookup_name.assert_called_once_with('volume', 'testvol')

    def test_volume_policy_good(self):
        self.load_policy({'volume': 'bool foo :: testvol'})
        data = {'foo': True}
        self.lookup_name.return_value = mock.sentinel.volume_info

        ret = kojihub.check_volume_policy(data)
        self.lookup_name.assert_called_once_with('volume', 'testvol')
        self.assertEqual(ret, mock.sentinel.volume_info)

        # and again with strict on
        self.lookup_name.reset_mock()
        ret = kojihub.check_volume_policy(data, strict=True)
        self.lookup_name.assert_called_once_with('volume', 'testvol')
        self.assertEqual(ret, mock.sentinel.volume_info)
