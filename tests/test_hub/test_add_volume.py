import unittest

import mock

import koji
import kojihub


class TestAddVolume(unittest.TestCase):

    def setUp(self):
        self.verify_name_internal = mock.patch('kojihub.kojihub.verify_name_internal').start()
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name').start()
        self.isdir = mock.patch('os.path.isdir').start()
        self.pathinfo_volumedir = mock.patch('koji.pathinfo.volumedir').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()

    def test_add_volume_wrong_format(self):
        volume_name = 'volume-name+'

        # name is longer as expected
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_volume(volume_name)

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_volume(volume_name)

    def test_non_exist_directory(self):
        volume_name = 'test-volume'
        self.isdir.return_value = False
        self.pathinfo_volumedir.return_value = 'path/to/volume'
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.add_volume(volume_name)
        self.assertEqual("please create the volume directory first", str(cm.exception))
        self.verify_name_internal.assert_called_once_with(volume_name)
        self.lookup_name.assert_not_called()

    def test_valid(self):
        volume_name = 'test-volume'
        volume_dict = {'id': 0, 'name': volume_name}
        self.isdir.return_value = True
        self.pathinfo_volumedir.return_value = 'path/to/volume'
        self.lookup_name.return_value = volume_dict
        rv = kojihub.add_volume(volume_name, strict=False)
        self.assertEqual(rv, volume_dict)
        self.verify_name_internal.assert_called_once_with(volume_name)
        self.lookup_name.assert_called_once_with('volume', volume_name, strict=False, create=True)

    def test_volume_exists(self):
        volume_name = 'test-volume'
        volume_dict = {'id': 0, 'name': volume_name}
        self.isdir.return_value = True
        self.pathinfo_volumedir.return_value = 'path/to/volume'
        self.lookup_name.return_value = volume_dict
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.add_volume(volume_name, strict=True)
        self.assertEqual(f'volume {volume_name} already exists', str(cm.exception))
        self.verify_name_internal.assert_called_once_with(volume_name)
        self.lookup_name.assert_called_once_with('volume', volume_name, strict=False)
