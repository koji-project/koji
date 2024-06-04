from __future__ import absolute_import
import unittest
import mock
import cgi

import koji
from io import BytesIO
from koji.server import ServerRedirect
from .loadwebindex import webidx


class TestActiveSessionDelete(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.assert_login = mock.patch.object(webidx, "_assertLogin").start()
        self.gen_html = mock.patch.object(webidx, '_genHTML').start()
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

    def get_fs(self, urlencode_data):
        urlencode_environ = {
            'CONTENT_LENGTH': str(len(urlencode_data)),
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'QUERY_STRING': '',
            'REQUEST_METHOD': 'POST',
        }
        data = BytesIO(urlencode_data)
        data.seek(0)
        return cgi.FieldStorage(fp=data, environ=urlencode_environ)

    def test_tagparent_remove(self):
        """Test tagparent function with remove action."""
        tag_id = 456
        parent_id = 123
        action = 'remove'
        data = [{'parent_id': parent_id}]
        self.get_server.return_value = self.server
        self.server.getTag.side_effect = [{'id': tag_id}, {'id': parent_id}]
        self.server.getInheritanceData.return_value = data
        self.server.setInheritanceData.return_value = None

        with self.assertRaises(ServerRedirect):
            webidx.tagparent(self.environ, tag_id, parent_id, action)
        self.assertEqual(self.environ['koji.redirect'], f'taginfo?tagID={tag_id}')
        self.server.getTag.assert_has_calls([mock.call(tag_id, strict=True),
                                             mock.call(parent_id, strict=True)])
        self.server.getInheritanceData.assert_called_once_with(tag_id)
        self.server.setInheritanceData.assert_called_once_with(tag_id, data)

    def test_tagparent_remove_tag_not_parent(self):
        """Test tagparent function with remove action."""
        tag_id = 456
        parent_id = 123
        action = 'remove'
        data = [{'parent_id': 111}]
        self.get_server.return_value = self.server
        self.server.getTag.side_effect = [{'id': tag_id}, {'id': parent_id}]
        self.server.getInheritanceData.return_value = data

        with self.assertRaises(koji.GenericError) as cm:
            webidx.tagparent(self.environ, tag_id, parent_id, action)
        self.assertEqual(str(cm.exception), f'tag {parent_id} is not a parent of tag {tag_id}')
        self.server.getTag.assert_has_calls([mock.call(tag_id, strict=True),
                                             mock.call(parent_id, strict=True)])
        self.server.getInheritanceData.assert_called_once_with(tag_id)
        self.server.setInheritanceData.assert_not_called()

    def test_tagparent_wrong_action(self):
        """Test tagparent function with remove action."""
        tag_id = 456
        parent_id = 123
        action = 'action'
        self.get_server.return_value = self.server
        self.server.getTag.side_effect = [{'id': tag_id}, {'id': parent_id}]

        with self.assertRaises(koji.GenericError) as cm:
            webidx.tagparent(self.environ, tag_id, parent_id, action)
        self.assertEqual(str(cm.exception), f'unknown action: {action}')
        self.server.getTag.assert_has_calls([mock.call(tag_id, strict=True),
                                             mock.call(parent_id, strict=True)])
        self.server.getInheritanceData.assert_not_called()
        self.server.setInheritanceData.assert_not_called()

    def test_tagparent_action_add(self):
        """Test tagparent function with add action."""
        tag_id = 456
        parent_id = 123
        action = 'add'
        data = [{'parent_id': 111}]
        urlencode_data = (b"add=true&priority=10&maxdepth=5&pkg_filter=pkg_filter&"
                          b"intransitive=true&noconfig=false")
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.getTag.side_effect = [{'id': tag_id}, {'id': parent_id}]
        self.server.getInheritanceData.return_value = data
        self.server.setInheritanceData.return_value = None

        with self.assertRaises(ServerRedirect):
            webidx.tagparent(self.environ, tag_id, parent_id, action)
        self.assertEqual(self.environ['koji.redirect'], f'taginfo?tagID={tag_id}')
        self.server.getTag.assert_has_calls([mock.call(tag_id, strict=True),
                                             mock.call(parent_id, strict=True)])
        self.server.getInheritanceData.assert_called_once_with(tag_id)
        self.server.setInheritanceData.assert_called_once_with(tag_id, data)

    def test_tagparent_action_add_form_cancel(self):
        """Test tagparent function with cancel action."""
        tag_id = 456
        parent_id = 123
        action = 'add'
        urlencode_data = b"cancel=true"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.getTag.side_effect = [{'id': tag_id}, {'id': parent_id}]

        with self.assertRaises(ServerRedirect):
            webidx.tagparent(self.environ, tag_id, parent_id, action)
        self.assertEqual(self.environ['koji.redirect'], f'taginfo?tagID={tag_id}')
        self.server.getTag.assert_has_calls([mock.call(tag_id, strict=True),
                                             mock.call(parent_id, strict=True)])

    def test_tagparent_action_edit_inheritance_0(self):
        """Test tagparent function with edit action."""
        tag_id = 456
        parent_id = 123
        action = 'add'
        data = [{'parent_id': 111, 'priority': 1}]

        urlencode_data = b"edit=true"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.getTag.side_effect = [{'id': tag_id}, {'id': parent_id}]
        self.server.getInheritanceData.return_value = data
        webidx.tagparent(self.environ, tag_id, parent_id, action)
        self.server.getTag.assert_has_calls([mock.call(tag_id, strict=True),
                                             mock.call(parent_id, strict=True)])
        self.server.getInheritanceData.assert_called_once_with(tag_id)

    def test_tagparent_action_edit_inheritance_1(self):
        """Test tagparent function with edit action."""
        tag_id = 456
        parent_id = 123
        action = 'add'
        data = [{'parent_id': 123, 'priority': 1}]

        urlencode_data = b"edit=true"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.getTag.side_effect = [{'id': tag_id}, {'id': parent_id}]
        self.server.getInheritanceData.return_value = data
        webidx.tagparent(self.environ, tag_id, parent_id, action)
        self.server.getTag.assert_has_calls([mock.call(tag_id, strict=True),
                                             mock.call(parent_id, strict=True)])
        self.server.getInheritanceData.assert_called_once_with(tag_id)

    def test_tagparent_action_edit_inheritance_more(self):
        """Test tagparent function with edit action."""
        tag_id = 456
        parent_id = 123
        action = 'add'
        data = [{'parent_id': 123, 'priority': 1},
                {'parent_id': 123, 'priority': 2},
                {'parent_id': 123, 'priority': 3}]

        urlencode_data = b"edit=true"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.getTag.side_effect = [{'id': tag_id}, {'id': parent_id}]
        self.server.getInheritanceData.return_value = data
        with self.assertRaises(koji.GenericError) as cm:
            webidx.tagparent(self.environ, tag_id, parent_id, action)
        self.assertEqual(str(cm.exception),
                         f'tag {tag_id} has tag {parent_id} listed as a parent more than once')
        self.server.getTag.assert_has_calls([mock.call(tag_id, strict=True),
                                             mock.call(parent_id, strict=True)])
        self.server.getInheritanceData.assert_called_once_with(tag_id)
