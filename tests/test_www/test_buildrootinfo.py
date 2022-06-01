import unittest
import koji

import mock
from .loadwebindex import webidx


class TestBuildrootInfo(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.assert_login = mock.patch.object(webidx, "_assertLogin").start()
        self.server = mock.MagicMock()
        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': None
        }
        self.buildroot_id = '1'

    def tearDown(self):
        mock.patch.stopall()

    def test_buildrootinfo_exception(self):
        """Test buildrootinfo function raises exception when buildroot ID is unknown."""
        self.get_server.return_value = self.server
        self.server.getBuildroot.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            webidx.buildrootinfo(self.environ, self.buildroot_id)
        self.assertEqual(str(cm.exception), f'unknown buildroot ID: {self.buildroot_id}')
