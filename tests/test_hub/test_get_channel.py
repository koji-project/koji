import unittest

import mock

import koji
import kojihub


class TestGetChannel(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        self.exports = kojihub.RootExports()

    def tearDown(self):
        mock.patch.stopall()

    def test_wrong_type_channelInfo(self):
        # dict
        channel_info = {'channel': 'val'}
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getChannel(channel_info)
        self.assertEqual('Invalid name or id value: %s' % channel_info,
                         str(cm.exception))

        # list
        channel_info = ['channel']
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getChannel(channel_info)
        self.assertEqual('Invalid name or id value: %s' % channel_info,
                         str(cm.exception))
