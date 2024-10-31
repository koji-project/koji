import unittest
import koji

from unittest import mock
from .loadwebindex import webidx
from koji.server import ServerRedirect
from kojiweb.util import FieldStorageCompat


class TestNotificationEdit(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.gen_html = mock.patch.object(webidx, '_genHTML').start()
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
        self.pkg_id = 2
        self.tag_id = 11

    def tearDown(self):
        mock.patch.stopall()

    def get_fs(self, query):
        return FieldStorageCompat({'QUERY_STRING': query})

    def test_notificationedit_exception(self):
        """Test notificationedit function raises exception when notification ID is not exists."""
        self.server.getBuildNotification.return_value = None
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.notificationedit(self.environ, self.notification_id)
        self.assertEqual(str(cm.exception), f'no notification with ID: {self.notification_id}')
        self.server.getBuildNotification.assert_called_once_with(int(self.notification_id))
        self.server.updateNotification.assert_not_called()
        self.server.listPackagesSimple.assert_not_called()
        self.server.listTags.assert_not_called()

    def test_notificationedit_save_case_int(self):
        """Test notificationedit function valid case (save)."""
        urlencode_data = "save=True&package=2&tag=11&success_only=True"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.getBuildNotification.return_value = {'id': self.notification_id}
        self.server.updateNotification.return_value = 1

        with self.assertRaises(ServerRedirect):
            webidx.notificationedit(self.environ, self.notification_id)
        self.assertEqual(self.environ['koji.redirect'], 'index')
        self.server.getBuildNotification.assert_called_once_with(int(self.notification_id))
        self.server.updateNotification.assert_called_once_with(self.notification_id, self.pkg_id,
                                                               self.tag_id, True)
        self.server.listPackagesSimple.assert_not_called()
        self.server.listTags.assert_not_called()

    def test_notificationedit_save_case_all(self):
        """Test notificationedit function valid case (all)."""
        urlencode_data = "save=True&package=all&tag=all"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.server.getBuildNotification.return_value = {'id': self.notification_id}
        self.get_server.side_effect = __get_server
        self.server.updateNotification.return_value = 1

        with self.assertRaises(ServerRedirect):
            webidx.notificationedit(self.environ, self.notification_id)
        self.assertEqual(self.environ['koji.redirect'], 'index')
        self.server.getBuildNotification.assert_called_once_with(int(self.notification_id))
        self.server.updateNotification.assert_called_once_with(
            self.notification_id, None, None, False)
        self.server.listPackagesSimple.assert_not_called()
        self.server.listTags.assert_not_called()

    def test_notificationedit_cancel_case(self):
        """Test notificationedit function valid case (cancel)."""
        urlencode_data = "cancel=True"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.server.getBuildNotification.return_value = {'id': self.notification_id}
        self.get_server.side_effect = __get_server

        with self.assertRaises(ServerRedirect):
            webidx.notificationedit(self.environ, self.notification_id)
        self.assertEqual(self.environ['koji.redirect'], 'index')
        self.server.getBuildNotification.assert_called_once_with(int(self.notification_id))
        self.server.updateNotification.assert_not_called()
        self.server.listPackagesSimple.assert_not_called()
        self.server.listTags.assert_not_called()

    def test_notificationedit_another_case(self):
        """Test notificationedit function valid case (another)."""
        urlencode_data = "another=True"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.server.getBuildNotification.return_value = {'id': self.notification_id}
        self.get_server.side_effect = __get_server

        webidx.notificationedit(self.environ, self.notification_id)
        self.server.getBuildNotification.assert_called_once_with(int(self.notification_id))
        self.server.updateNotification.assert_not_called()
        self.server.listPackagesSimple.assert_called_once_with(queryOpts={'order': 'package_name'})
        self.server.listTags.assert_called_once_with(queryOpts={'order': 'name'})
