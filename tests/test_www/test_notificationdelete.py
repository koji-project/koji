import unittest
import koji

import mock
from .loadwebindex import webidx
from koji.server import ServerRedirect


class TestNotificationDelete(unittest.TestCase):
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
        self.notification_id = '1'

    def tearDown(self):
        mock.patch.stopall()

    def test_notificationdelete_exception(self):
        """Test notificationdelete function raises exception when notification ID not exists."""
        self.server.getBuildNotification.return_value = None
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.notificationdelete(self.environ, self.notification_id)
        self.assertEqual(str(cm.exception), f'no notification with ID: {self.notification_id}')

    def test_notificationdelete_valid(self):
        """Test notificationdelete function valid case."""
        self.server.getBuildNotification.return_value = {'id': self.notification_id}
        self.get_server.return_value = self.server

        with self.assertRaises(ServerRedirect):
            webidx.notificationdelete(self.environ, self.notification_id)
        self.server.deleteNotification.assert_called_with(self.notification_id)
        self.assertEqual(self.environ['koji.redirect'], 'index')
