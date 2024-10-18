import unittest
import koji

from unittest import mock
from .loadwebindex import webidx


class TestBuildInfo(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.server = mock.MagicMock()
        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': None
        }
        self.build_id = '1'

    def tearDown(self):
        mock.patch.stopall()

    def test_buildinfo_exception(self):
        """Test taskinfo function raises exception"""
        self.server.getBuild.side_effect = koji.GenericError
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.buildinfo(self.environ, self.build_id)
        self.assertEqual(str(cm.exception), f'No such build ID: {self.build_id}')
