import unittest

import koji
import kojihub


class TestGetChannel(unittest.TestCase):

    def test_wrong_type_channelInfo(self):
        # dict
        channel_info = {'channel': 'val'}
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_channel(channel_info)
        self.assertEqual('Invalid type for channelInfo: %s' % type(channel_info),
                         str(cm.exception))

        #list
        channel_info = ['channel']
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_channel(channel_info)
        self.assertEqual('Invalid type for channelInfo: %s' % type(channel_info),
                         str(cm.exception))
