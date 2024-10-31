from unittest import mock
import unittest

import koji
from .loadwebindex import webidx
from koji.server import ServerRedirect
from kojiweb.util import FieldStorageCompat


class TestNotificationCreate(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.gen_html = mock.patch.object(webidx, '_genHTML').start()
        self.assert_login = mock.patch.object(webidx, "_assertLogin").start()
        self.server = mock.MagicMock()
        self.buildtag_id = '11'
        self.pkg_id = '2'
        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': {'id': '1'},
        }

    def tearDown(self):
        mock.patch.stopall()

    def get_fs(self, query):
        return FieldStorageCompat({'QUERY_STRING': query})

    def test_notificationcreate_add_case_not_logged(self):
        """Test notificationcreate function raises exception when user is not logged."""
        environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': None,
        }
        urlencode_data = "add=True&package=2&tag=11"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.notificationcreate(environ)
        self.assertEqual(str(cm.exception), 'not logged-in')
        self.server.createNotification.assert_not_called()
        self.server.listPackagesSimple.assert_not_called()
        self.server.listTags.assert_not_called()

    def test_notificationcreate_add_case_int(self):
        """Test notificationcreate function valid case (add)"""
        urlencode_data = "add=True&package=2&tag=11&success_only=True"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.createNotification.return_value = 11

        with self.assertRaises(ServerRedirect):
            webidx.notificationcreate(self.environ)
        self.assertEqual(self.environ['koji.redirect'], 'index')
        self.server.createNotification.assert_called_with('1', int(self.pkg_id),
                                                          int(self.buildtag_id), True)
        self.server.listPackagesSimple.assert_not_called()
        self.server.listTags.assert_not_called()

    def test_notificationcreate_add_case_all(self):
        """Test notificationcreate function valid case (add)"""
        urlencode_data = "add=True&package=all&tag=all"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.createNotification.return_value = 11

        with self.assertRaises(ServerRedirect):
            webidx.notificationcreate(self.environ)
        self.assertEqual(self.environ['koji.redirect'], 'index')
        self.server.createNotification.assert_called_with('1', None, None, False)
        self.server.listPackagesSimple.assert_not_called()
        self.server.listTags.assert_not_called()

    def test_notificationcreate_cancel_case(self):
        """Test notificationcreate function valid case (cancel)."""
        urlencode_data = "cancel=True"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server

        with self.assertRaises(ServerRedirect):
            webidx.notificationcreate(self.environ)
        self.assertEqual(self.environ['koji.redirect'], 'index')
        self.server.createNotification.assert_not_called()
        self.server.listPackagesSimple.assert_not_called()
        self.server.listTags.assert_not_called()

    def test_notificationcreate_another_case(self):
        """Test notificationcreate function valid case (another)."""
        urlencode_data = "another=True"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server

        webidx.notificationcreate(self.environ)
        self.server.createNotification.assert_not_called()
        self.server.listPackagesSimple.assert_called_once_with(queryOpts={'order': 'package_name'})
        self.server.listTags.assert_called_once_with(queryOpts={'order': 'name'})
