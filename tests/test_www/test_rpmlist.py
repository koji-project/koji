import unittest
import koji

import mock
from .loadwebindex import webidx


class TestRpmList(unittest.TestCase):
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
        self.image_id = '2'

    def tearDown(self):
        mock.patch.stopall()

    def test_rpmlist_exception_unknown_buildroot_id(self):
        """Test rpmlist function raises exception when buildroot_id is unknown."""
        self.get_server.return_value = self.server
        self.server.getBuildroot.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            webidx.rpmlist(self.environ, type='component', buildrootID=self.buildroot_id)
        self.assertEqual(str(cm.exception), f'unknown buildroot ID: {self.buildroot_id}')

    def test_rpmlist_exception_wrong_type(self):
        """Test rpmlist function raises exception when buildroot type is wrong type."""
        self.get_server.return_value = self.server
        self.server.getBuildroot.return_value = {'id': int(self.buildroot_id)}

        with self.assertRaises(koji.GenericError) as cm:
            webidx.rpmlist(self.environ, type='non-exist', buildrootID=self.buildroot_id)
        self.assertEqual(str(cm.exception), 'unrecognized type of rpmlist')

    def test_rpmlist_exception_unknown_image_id(self):
        """Test rpmlist function raises exception when image_id is unknown."""
        self.get_server.return_value = self.server
        self.server.getArchive.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            webidx.rpmlist(self.environ, type='image', imageID=self.image_id)
        self.assertEqual(str(cm.exception), f'unknown image ID: {self.image_id}')

    def test_rpmlist_exception_unknown_image_type(self):
        """Test rpmlist function raises exception when image type is unknown."""
        self.get_server.return_value = self.server
        self.server.getArchive.return_value = {'id': int(self.image_id)}

        with self.assertRaises(koji.GenericError) as cm:
            webidx.rpmlist(self.environ, type='non-exist', imageID=self.image_id)
        self.assertEqual(str(cm.exception), 'unrecognized type of image rpmlist')

    def test_rpmlist_exception_buildroot_and_image_none(self):
        """Test rpmlist function raises exception when buildroot and image is None."""
        self.get_server.return_value = self.server

        with self.assertRaises(koji.GenericError) as cm:
            webidx.rpmlist(self.environ, type='non-exist')
        self.assertEqual(str(cm.exception), 'Both buildrootID and imageID are None')
