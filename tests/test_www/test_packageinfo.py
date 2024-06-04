import mock
import unittest

import koji
from .loadwebindex import webidx


class TestPackageInfo(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.gen_html = mock.patch.object(webidx, '_genHTML').start()
        self.server = mock.MagicMock()

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
        self.server.getPackage.return_value = None

        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.packageinfo(self.environ, self.package_id)
        self.assertEqual(str(cm.exception), f'No such package ID: {self.package_id}')
        self.server.getPackage.assert_called_once_with(int(self.package_id))

    def test_packageinfo_valid(self):
        """Test taskinfo function"""
        self.server.getPackage.return_value = {'id': self.package_id, 'name': 'test-pkg'}

        self.get_server.return_value = self.server
        webidx.packageinfo(self.environ, self.package_id)
        self.server.getPackage.assert_called_once_with(int(self.package_id))
