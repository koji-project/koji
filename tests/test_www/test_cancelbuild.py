import unittest
import koji

from unittest import mock
from .loadwebindex import webidx
from koji.server import ServerRedirect


class TestCancelBuild(unittest.TestCase):
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
        self.build_id = '1'

    def tearDown(self):
        mock.patch.stopall()

    def test_cancelbuild_exception_unknown_build(self):
        """Test cancelbuild function raises exception when build ID is unknown."""
        self.get_server.return_value = self.server
        self.server.getBuild.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            webidx.cancelbuild(self.environ, self.build_id)
        self.assertEqual(str(cm.exception), f'unknown build ID: {self.build_id}')

    def test_cancelbuild_unable_cancel(self):
        """Test cancelbuild function raises exception when unable to cancel build."""
        self.get_server.return_value = self.server
        self.server.getBuild.return_value = {'id': int(self.build_id)}
        self.server.cancelBuild.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            webidx.cancelbuild(self.environ, self.build_id)
        self.assertEqual(str(cm.exception), 'unable to cancel build')

    def test_cancelbuild_valid(self):
        """Test cancelbuild function valid case."""
        self.server.getBuild.return_value = {'id': int(self.build_id)}
        self.server.cancelBuild.return_value = int(self.build_id)
        self.get_server.return_value = self.server

        with self.assertRaises(ServerRedirect):
            webidx.cancelbuild(self.environ, self.build_id)
        self.server.getBuild.assert_called_with(int(self.build_id))
        self.server.cancelBuild.assert_called_with(int(self.build_id))
        self.assertEqual(self.environ['koji.redirect'], f'buildinfo?buildID={self.build_id}')
