import unittest

import mock
from .loadwebindex import webidx
from koji.server import ServerRedirect


class TestFreeTask(unittest.TestCase):
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
        self.task_id = '1'

    def tearDown(self):
        mock.patch.stopall()

    def test_freetask_valid(self):
        """Test freetask function valid case."""
        self.server.freeTask.return_value = None
        self.get_server.return_value = self.server

        with self.assertRaises(ServerRedirect):
            webidx.freetask(self.environ, self.task_id)
        self.server.freeTask.assert_called_with(int(self.task_id))
        self.assertEqual(self.environ['koji.redirect'], f'taskinfo?taskID={self.task_id}')
