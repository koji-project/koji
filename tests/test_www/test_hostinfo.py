import mock
import unittest

import koji
from .loadwebindex import webidx


class TestHostInfo(unittest.TestCase):
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
        self.host_id = '11'
        self.user_id = '111'

    def tearDown(self):
        mock.patch.stopall()

    def test_hostinfo_exception_host_option(self):
        """Test taskinfo function raises exception"""
        self.server.getHost.return_value = None
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.hostinfo(self.environ, hostID=self.host_id)
        self.assertEqual(str(cm.exception), f'No such host ID: {self.host_id}')

    def test_hostinfo_exception_user_option(self):
        """Test taskinfo function raises exception"""
        self.server.listHosts.return_value = []
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.hostinfo(self.environ, userID=self.user_id)
        self.assertEqual(str(cm.exception), f'No such host for user ID: {self.user_id}')

    def test_hostinfo_exception(self):
        """Test hostinfo function raises exception"""
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.hostinfo(self.environ)
        self.assertEqual(str(cm.exception), 'hostID or userID must be provided')

    def test_hostinfo_valid(self):
        """Test hostinfo function"""
        self.get_server.return_value = self.server
        self.server.listHosts.return_value = [
            {'id': 11, 'name': 'test-host', 'update_ts': 1234567890}]
        self.server.listChannels.return_value = [
            {'id': 123, 'name': 'test-channel-123', 'enabled': True},
            {'id': 456, 'name': 'test-channel-456', 'enabled': False}]
        self.server.listBuildroots.return_value = [{'id': 111, 'create_event_time': 11111111},
                                                   {'id': 222, 'create_event_time': 22222222}]
        webidx.hostinfo(self.environ, userID=self.user_id)
        self.server.getHost.assert_not_called()
        self.server.listHosts.assert_called_once_with(userID=int(self.user_id))
        self.server.listChannels.assert_called_once_with(int(self.host_id))
        self.server.listBuildroots.assert_called_once_with(
            hostID=int(self.host_id), state=[0, 1, 2])
        self.server.getUserPerms.assert_not_called()

    def test_hostinfo_valid_2(self):
        """Test hostinfo function"""
        environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': {'id': 5}
        }
        self.get_server.return_value = self.server
        self.server.getHost.return_value = {'id': 11, 'name': 'test-host', 'update_ts': 1234567890}
        self.server.listChannels.return_value = [
            {'id': 123, 'name': 'test-channel-123', 'enabled': True},
            {'id': 456, 'name': 'test-channel-456', 'enabled': False}]
        self.server.listBuildroots.return_value = [{'id': 111, 'create_event_time': 11111111},
                                                   {'id': 222, 'create_event_time': 22222222}]
        self.server.getUserPerms.return_value = ['perm-1', 'perm-2']
        webidx.hostinfo(environ, hostID=self.host_id)
        self.server.getHost.assert_called_once_with(int(self.host_id))
        self.server.listHosts.assert_not_called()
        self.server.listChannels.assert_called_once_with(int(self.host_id))
        self.server.listBuildroots.assert_called_once_with(
            hostID=int(self.host_id), state=[0, 1, 2])
        self.server.getUserPerms.assert_called_once_with(5)
