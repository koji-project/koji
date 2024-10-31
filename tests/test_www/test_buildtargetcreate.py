from unittest import mock
import unittest

import koji
from .loadwebindex import webidx
from koji.server import ServerRedirect
from kojiweb.util import FieldStorageCompat


class TestBuildTargetCreate(unittest.TestCase):
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

    def get_fs(self, query):
        return FieldStorageCompat({'QUERY_STRING': query})

    def test_buildtargetcreate_add_case_exception(self):
        """Test buildtargetcreate function raises exception when buildtarget is not created."""
        urlencode_data = "add=True&name=testname&buildTag=11&destTag=99"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.createBuildTarget.return_value = 1
        self.server.getBuildTarget.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            webidx.buildtargetcreate(self.environ)
        self.server.createBuildTarget.assert_called_with('testname', int(self.buildtag_id),
                                                         int(self.desttag_id))
        self.server.getBuildTarget.assert_called_with('testname')
        self.server.listTags.assert_not_called()
        self.assertEqual(str(cm.exception), 'error creating build target "testname"')

    def test_buildtargetcreate_add_case_valid(self):
        """Test buildtargetcreate function valid case (add)."""
        urlencode_data = "add=True&name=testname&buildTag=11&destTag=99"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.createBuildTarget.return_value = 1
        self.server.getBuildTarget.return_value = {'id': 1}

        with self.assertRaises(ServerRedirect):
            webidx.buildtargetcreate(self.environ)
        self.server.createBuildTarget.assert_called_with('testname', int(self.buildtag_id),
                                                         int(self.desttag_id))
        self.server.getBuildTarget.assert_called_with('testname')
        self.server.listTags.assert_not_called()
        self.assertEqual(self.environ['koji.redirect'], 'buildtargetinfo?targetID=1')

    def test_buildtargetcreate_cancel_case(self):
        """Test buildtargetcreate function valid case (cancel)."""
        urlencode_data = "cancel=True"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server

        with self.assertRaises(ServerRedirect):
            webidx.buildtargetcreate(self.environ)
        self.server.createBuildTarget.assert_not_called()
        self.server.getBuildTarget.assert_not_called()
        self.server.listTags.assert_not_called()
        self.assertEqual(self.environ['koji.redirect'], 'buildtargets')

    def test_buildtargetcreate_another_case(self):
        """Test buildtargetcreate function valid case (another)."""
        urlencode_data = "another=True"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.listTags.return_value = [{'id': 1, 'name': 'test-tag-1'},
                                             {'id': 2, 'name': 'test-tag-2'}]
        webidx.buildtargetcreate(self.environ)
        self.server.createBuildTarget.assert_not_called()
        self.server.getBuildTarget.assert_not_called()
        self.server.listTags.assert_called_with()
