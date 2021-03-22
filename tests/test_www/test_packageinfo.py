import mock
import unittest

import koji
from .loadwebindex import webidx


class TestPackageInfo(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()

        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': None
        }
        self.package_id = '1'

    def tearDown(self):
        mock.patch.stopall()

    def test_packageinfo_exception(self):
        """Test taskinfo function raises exception"""
        server = mock.MagicMock()
        server.getPackage.return_value = None

        self.get_server.return_value = server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.packageinfo(self.environ, self.package_id)
        self.assertEqual(
            str(cm.exception), 'No such package ID: %s' % self.package_id)
