import unittest

import mock
from .loadwebindex import webidx
from koji.server import ServerRedirect


class TestResubmitTask(unittest.TestCase):
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
        self.task_id = 1

    def tearDown(self):
        mock.patch.stopall()

    def test_resubmittask_valid(self):
        """Test resubmittask function valid case."""
        self.server.resubmitTask.return_value = 2
        self.get_server.return_value = self.server

        with self.assertRaises(ServerRedirect):
            webidx.resubmittask(self.environ, str(self.task_id))
        self.server.resubmitTask.assert_called_with(self.task_id)
        self.assertEqual(self.environ['koji.redirect'], 'taskinfo?taskID=2')
