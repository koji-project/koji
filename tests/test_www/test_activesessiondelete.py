from __future__ import absolute_import
import unittest
import mock

from koji.server import ServerRedirect
from .loadwebindex import webidx


class TestActiveSessionDelete(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.assert_login = mock.patch.object(webidx, "_assertLogin").start()
        self.server = mock.MagicMock()
        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': None,

        }

        def __get_server(env):
            env['koji.session'] = self.server
            return self.server

        self.get_server.side_effect = __get_server

    def tearDown(self):
        mock.patch.stopall()

    def test_activesessiondelete(self):
        """Test activesessiondelete function."""
        session_id = 1
        self.get_server.return_value = self.server
        self.server.logout.return_value = None

        with self.assertRaises(ServerRedirect):
            webidx.activesessiondelete(self.environ, session_id)
        self.assertEqual(self.environ['koji.redirect'], 'activesession')
        self.server.logout.assert_called_with(session_id=session_id)
