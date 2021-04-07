import mock
import unittest

import koji
from .loadwebindex import webidx


class TestHostInfo(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()

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
        server = mock.MagicMock()
        server.getHost.return_value = None

        self.get_server.return_value = server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.hostinfo(self.environ, hostID=self.host_id)
        self.assertEqual(
            str(cm.exception), 'No such host ID: %s' % self.host_id)

    def test_hostinfo_exception_user_option(self):
        """Test taskinfo function raises exception"""
        server = mock.MagicMock()
        server.listHosts.return_value = []

        self.get_server.return_value = server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.hostinfo(self.environ, userID=self.user_id)
        self.assertEqual(
            str(cm.exception), 'No such host for user ID: %s' % self.user_id)

    def test_hostinfo_exception(self):
        """Test taskinfo function raises exception"""
        server = mock.MagicMock()

        self.get_server.return_value = server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.hostinfo(self.environ)
        self.assertEqual(str(cm.exception), 'hostID or userID must be provided')
