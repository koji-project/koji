import unittest
import koji

from unittest import mock
from .loadwebindex import webidx
from koji.server import ServerRedirect
from kojiweb.util import FieldStorageCompat


class TestTagEdit(unittest.TestCase):
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
        self.tag_id = '1'

    def tearDown(self):
        mock.patch.stopall()

    def get_fs(self, query):
        environ = {'QUERY_STRING': query}
        return FieldStorageCompat(environ)

    def test_tagedit_exception(self):
        """Test tagedit function raises exception when tag ID not exists."""
        self.get_server.return_value = self.server
        self.server.getTag.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            webidx.tagedit(self.environ, self.tag_id)
        self.assertEqual(str(cm.exception), f'no tag with ID: {self.tag_id}')
        self.server.mavenEnabled.assert_called_once_with()
        self.server.getTag.assert_called_once_with(int(self.tag_id))
        self.server.getAllPerms.assert_not_called()
        self.server.editTag2.assert_not_called()

    def test_tagedit_add_case_valid(self):
        """Test tagedit function valid case (save)."""
        urlencode_data = "save=True&name=testname&arches=x86_64&locked=True&permission=1" \
                         "&maven_support=True&maven_include_all=True"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.editTag2.return_value = None
        self.server.getTag.return_value = {'id': int(self.tag_id)}

        with self.assertRaises(ServerRedirect):
            webidx.tagedit(self.environ, self.tag_id)
        self.assertEqual(self.environ['koji.redirect'], f'taginfo?tagID={self.tag_id}')
        self.server.mavenEnabled.assert_called_once_with()
        self.server.getTag.assert_called_once_with(int(self.tag_id))
        self.server.getAllPerms.assert_not_called()
        self.server.editTag2.assert_called_with(1, arches='x86_64', locked=True, perm=1,
                                                maven_support=True, maven_include_all=True,
                                                name='testname')

    def test_tagedit_cancel_case_valid(self):
        """Test tagedit function valid case (cancel)."""
        urlencode_data = "cancel=True"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.getTag.return_value = {'id': int(self.tag_id)}

        with self.assertRaises(ServerRedirect):
            webidx.tagedit(self.environ, self.tag_id)
        self.server.editTag2.assert_not_called()
        self.assertEqual(self.environ['koji.redirect'], f'taginfo?tagID={self.tag_id}')
        self.server.mavenEnabled.assert_called_once_with()
        self.server.getTag.assert_called_once_with(int(self.tag_id))
        self.server.getAllPerms.assert_not_called()
        self.server.editTag2.assert_not_called()

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
        self.server.getTag.return_value = {'id': int(self.tag_id)}
        self.server.getAllPerms.return_value = [{'id': 1, 'name': 'test-perm-1'},
                                                {'id': 2, 'name': 'test-perm-2'},
                                                {'id': 3, 'name': 'test-perm-3'}]

        webidx.tagedit(self.environ, self.tag_id)
        self.server.mavenEnabled.assert_called_once_with()
        self.server.getTag.assert_called_once_with(int(self.tag_id))
        self.server.getAllPerms.assert_called_once_with()
        self.server.editTag2.assert_not_called()
