import unittest

from unittest import mock
from .loadwebindex import webidx
from koji.server import ServerRedirect


class TestEnableHost(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.assert_login = mock.patch.object(webidx, "_assertLogin").start()
        self.server = mock.MagicMock()
        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': None
        }
        self.host_id = '1'
        self.host_info = {'id': int(self.host_id), 'name': 'test-host'}

    def tearDown(self):
        mock.patch.stopall()

    def test_enablehost_valid(self):
        """Test enablehost function valid case."""
        self.server.getHost.return_value = self.host_info
        self.server.enableHost.return_value = None
        self.get_server.return_value = self.server

        with self.assertRaises(ServerRedirect):
            webidx.enablehost(self.environ, self.host_id)
        self.server.enableHost.assert_called_with(self.host_info['name'])
        self.assertEqual(self.environ['koji.redirect'], f'hostinfo?hostID={self.host_id}')
