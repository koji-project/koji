import mock
import unittest
import cgi

import koji
from io import BytesIO
from .loadwebindex import webidx


class TestBuildTargetEdit(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.assert_login = mock.patch.object(webidx, "_assertLogin").start()
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

        urlencode_data = b"save=True&name=testname&buildTag=11&destTag=99"
        urlencode_environ = {
            'CONTENT_LENGTH': str(len(urlencode_data)),
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'QUERY_STRING': '',
            'REQUEST_METHOD': 'POST',
        }
        data = BytesIO(urlencode_data)
        data.seek(0)
        self.fs = cgi.FieldStorage(fp=data, environ=urlencode_environ)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = self.fs
            return self.server

        self.get_server.side_effect = __get_server

    def tearDown(self):
        mock.patch.stopall()

    def test_buildtargetedit_exception(self):
        """Test taskinfo function raises exception"""
        self.server.getBuildTarget.return_value = None
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.buildtargetedit(self.environ, self.buildtarget_id)
        self.assertEqual(str(cm.exception), 'No such build target: %s' % self.buildtarget_id)

    def test_buildtargetedit_exception_build_tag(self):
        """Test taskinfo function raises exception"""
        self.server.getBuildTarget.return_value = {'id': 1}
        self.server.getTag.return_value = None
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.buildtargetedit(self.environ, self.buildtarget_id)
        self.assertEqual(str(cm.exception), 'No such tag ID: %s' % self.buildtag_id)

    def test_buildtargetedit_exception_dest_tag(self):
        """Test taskinfo function raises exception"""
        self.server.getBuildTarget.return_value = {'id': 1}
        self.server.getTag.side_effect = [{'id': 11}, None]
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.buildtargetedit(self.environ, self.buildtarget_id)
        self.assertEqual(str(cm.exception), 'No such tag ID: %s' % self.desttag_id)
