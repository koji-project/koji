from unittest import mock
import unittest
import cgi

import koji
from io import BytesIO
from .loadwebindex import webidx
from koji.server import ServerRedirect


class TestBuildTargetEdit(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.assert_login = mock.patch.object(webidx, "_assertLogin").start()
        self.gen_html = mock.patch.object(webidx, '_genHTML').start()
        self.server = mock.MagicMock()
        self.buildtarget_id = '1'
        self.buildtag_id = '11'
        self.desttag_id = '99'
        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': None,
        }

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

    def test_buildtargetedit_exception(self):
        """Test buildtargetedit function raises exception when build target not exists."""
        urlencode_data = b"save=True&name=testname&buildTag=11&destTag=99"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.getBuildTarget.return_value = None
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.buildtargetedit(self.environ, self.buildtarget_id)
        self.assertEqual(str(cm.exception), f'No such build target: {self.buildtarget_id}')
        self.server.getBuildTarget.assert_called_with(int(self.buildtarget_id))
        self.server.getTag.assert_not_called()
        self.server.editBuildTarget.assert_not_called()
        self.server.listTags.assert_not_called()

    def test_buildtargetedit_exception_build_tag(self):
        """Test buildtargetedit function raises exception when build tag not exists."""
        urlencode_data = b"save=True&name=testname&buildTag=11&destTag=99"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.getBuildTarget.return_value = {'id': int(self.buildtarget_id)}
        self.server.getTag.return_value = None
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.buildtargetedit(self.environ, self.buildtarget_id)
        self.assertEqual(str(cm.exception), f'No such tag ID: {self.buildtag_id}')
        self.server.getBuildTarget.assert_called_with(int(self.buildtarget_id))
        self.server.getTag.assert_called_with(int(self.buildtag_id))
        self.server.editBuildTarget.assert_not_called()
        self.server.listTags.assert_not_called()

    def test_buildtargetedit_exception_dest_tag(self):
        """Test buildtargetedit function raises exception when destination tag not exists."""
        urlencode_data = b"save=True&name=testname&buildTag=11&destTag=99"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.getBuildTarget.return_value = {'id': int(self.buildtarget_id)}
        self.server.getTag.side_effect = [{'id': int(self.buildtag_id)}, None]
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.buildtargetedit(self.environ, self.buildtarget_id)
        self.assertEqual(str(cm.exception), f'No such tag ID: {self.desttag_id}')
        self.server.getBuildTarget.assert_called_with(int(self.buildtarget_id))
        self.server.getTag.assert_has_calls([mock.call(int(self.buildtag_id)),
                                             mock.call(int(self.desttag_id))])
        self.server.editBuildTarget.assert_not_called()
        self.server.listTags.assert_not_called()

    def test_buildtargetedit_save_case_valid(self):
        """Test buildtargetedit function valid case (save)."""
        urlencode_data = b"save=True&name=testname&buildTag=11&destTag=99"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server

        self.server.getBuildTarget.return_value = {'id': int(self.buildtarget_id)}
        self.server.getTag.side_effect = [{'id': int(self.buildtag_id)},
                                          {'id': int(self.desttag_id)}]
        self.server.editBuildTarget.return_value = None
        self.get_server.return_value = self.server

        with self.assertRaises(ServerRedirect):
            webidx.buildtargetedit(self.environ, self.buildtarget_id)
        self.assertEqual(self.environ['koji.redirect'],
                         f'buildtargetinfo?targetID={self.buildtarget_id}')
        self.server.getBuildTarget.assert_called_with(int(self.buildtarget_id))
        self.server.getTag.assert_has_calls([mock.call(int(self.buildtag_id)),
                                             mock.call(int(self.desttag_id))])
        self.server.editBuildTarget.assert_called_with(int(self.buildtarget_id), 'testname',
                                                       int(self.buildtag_id), int(self.desttag_id))
        self.server.listTags.assert_not_called()

    def test_buildtargetedit_cancel_case(self):
        """Test buildtargetedit function valid case (cancel)."""
        self.server.getBuildTarget.return_value = {'id': int(self.buildtarget_id)}
        urlencode_data = b"cancel=True"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server

        with self.assertRaises(ServerRedirect):
            webidx.buildtargetedit(self.environ, self.buildtarget_id)
        self.assertEqual(self.environ['koji.redirect'],
                         f'buildtargetinfo?targetID={self.buildtarget_id}')
        self.server.getBuildTarget.assert_called_with(int(self.buildtarget_id))
        self.server.getTag.assert_not_called()
        self.server.editBuildTarget.assert_not_called()
        self.server.listTags.assert_not_called()

    def test_buildtargetedit_another_case(self):
        """Test buildtargetedit function valid case (another)."""
        urlencode_data = b"another=True"
        fs = self.get_fs(urlencode_data)
        self.server.getBuildTarget.return_value = {'id': int(self.buildtarget_id)}

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.listTags.return_value = [{'id': 1, 'name': 'test-tag-1'},
                                             {'id': 2, 'name': 'test-tag-2'}]
        webidx.buildtargetedit(self.environ, self.buildtarget_id)
        self.server.getBuildTarget.assert_called_with(int(self.buildtarget_id))
        self.server.getTag.assert_not_called()
        self.server.editBuildTarget.assert_not_called()
        self.server.listTags.assert_called_with()
