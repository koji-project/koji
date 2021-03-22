import mock
import unittest
import cgi

import koji
from io import BytesIO
from .loadwebindex import webidx


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.server = mock.MagicMock()
        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': None,
        }
        urlencode_data = b"terms=test&type=package&match=testmatch"
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
            env['koji.form'] = self.fs
            return self.server

        self.get_server.side_effect = __get_server

    def tearDown(self):
        mock.patch.stopall()

    def test_search_exception_match(self):
        """Test taskinfo function raises exception"""
        self.server.getBuildTarget.return_info = None
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.search(self.environ)
        self.assertEqual(str(cm.exception), "No such match type: 'testmatch'")
