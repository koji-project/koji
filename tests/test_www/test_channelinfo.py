import mock
import unittest

import koji
from .loadwebindex import webidx


class TestChannelInfo(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.gen_html = mock.patch.object(webidx, '_genHTML').start()
        self.server = mock.MagicMock()
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
        """Test channelinfo function raises exception"""
        self.get_server.return_value = self.server
        self.server.getChannel.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            webidx.channelinfo(self.environ, self.channel_id)
        self.assertEqual(str(cm.exception), f'No such channel ID: {self.channel_id}')
        self.server.getChannel.assert_called_once_with(int(self.channel_id))
        self.server.listTasks.assert_not_called()
        self.server.listHosts.assert_not_called()

    def test_channel_info_valid(self):
        """Test channelinfo function valid"""
        self.get_server.return_value = self.server
        self.server.getChannel.return_value = {'name': 'test-channel', 'id': self.channel_id}
        self.server.listTasks.return_value = 5
        self.server.listHosts.return_value = [
            {'id': 1, 'name': 'test-host-1', 'enabled': True, 'ready': True},
            {'id': 2, 'name': 'test-host-2', 'enabled': False, 'ready': False},
            {'id': 3, 'name': 'test-host-3', 'enabled': True, 'ready': False}]

        webidx.channelinfo(self.environ, self.channel_id)
        self.server.getChannel.assert_called_once_with(int(self.channel_id))
        self.server.listTasks.assert_called_once_with(
            opts={'channel_id': int(self.channel_id), 'state': [0, 1, 4]},
            queryOpts={'countOnly': True})
        self.server.listHosts.assert_called_once_with(channelID=int(self.channel_id))
