from unittest import mock
import unittest

import koji
from .loadwebindex import webidx
from kojiweb.util import FieldStorageCompat


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
        urlencode_data = "terms=test&type=package&match=testmatch"
        self.fs = FieldStorageCompat({'QUERY_STRING': urlencode_data})

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
