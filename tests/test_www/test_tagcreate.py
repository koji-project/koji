import unittest

from unittest import mock
from .loadwebindex import webidx
from koji.server import ServerRedirect
from kojiweb.util import FieldStorageCompat


class TestTagCreate(unittest.TestCase):
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

    def tearDown(self):
        mock.patch.stopall()

    def get_fs(self, query):
        return FieldStorageCompat({'QUERY_STRING': query})

    def test_tagcreate_add_case_valid(self):
        """Test tagcreate function valid case (add)"""
        urlencode_data = "add=True&name=testname&arches=x86_64&locked=True&permission=1" \
                         "&maven_support=True&maven_include_all=True"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.createTag.return_value = 1

        with self.assertRaises(ServerRedirect):
            webidx.tagcreate(self.environ)
        self.assertEqual(self.environ['koji.redirect'], 'taginfo?tagID=1')
        self.server.mavenEnabled.assert_called_once_with()
        self.server.createTag.assert_called_with('testname', arches='x86_64', locked=True,
                                                 perm=1, maven_support=True,
                                                 maven_include_all=True)
        self.server.getAllPerms.assert_not_called()

    def test_tagcreate_cancel_case_valid(self):
        """Test tagcreate function valid cases (cancel)."""
        urlencode_data = "cancel=True"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server

        with self.assertRaises(ServerRedirect):
            webidx.tagcreate(self.environ)
        self.assertEqual(self.environ['koji.redirect'], 'tags')
        self.server.mavenEnabled.assert_called_once_with()
        self.server.createTag.assert_not_called()
        self.server.getAllPerms.assert_not_called()

    def test_tagedit_another_case_valid(self):
        """Test tagedit function valid case (another)."""
        urlencode_data = "another=True"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.mavenEnabled.return_value = True
        self.server.getAllPerms.return_value = [{'id': 1, 'name': 'test-perm-1'},
                                                {'id': 2, 'name': 'test-perm-2'},
                                                {'id': 3, 'name': 'test-perm-3'}]

        webidx.tagcreate(self.environ)
        self.server.mavenEnabled.assert_called_once_with()
        self.server.createTag.assert_not_called()
        self.server.getAllPerms.assert_called_once_with()
