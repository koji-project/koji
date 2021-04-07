import mock
import unittest

import koji
from .loadwebindex import webidx


class TestChannelInfo(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': None
        }
        self.channel_id = '1'

    def tearDown(self):
        mock.patch.stopall()

    def test_channelinfo_exception(self):
        """Test taskinfo function raises exception"""
        server = mock.MagicMock()
        self.get_server.return_value = server
        server.getChannel.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            webidx.channelinfo(self.environ, self.channel_id)
        self.assertEqual(str(cm.exception), 'No such channel ID: %s' % self.channel_id)
