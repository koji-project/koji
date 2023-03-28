import unittest
import mock

import koji
import kojihub


class TestGetVolume(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name').start()

    def test_non_exist_volume_with_strict(self):
        volume = ['test-volume']
        self.lookup_name.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getVolume(volume, strict=True)
        self.assertEqual("No such volume: %s" % volume, str(cm.exception))

    def test_non_exist_volume_without_strict(self):
        volume = ['test-volume']
        self.lookup_name.return_value = None
        result = self.exports.getVolume(volume)
        self.assertEqual(None, result)

    def test_valid_volume(self):
        volume = ['test-volume']
        volume_dict = {'id': 0, 'name': 'DEFAULT'}
        self.lookup_name.return_value = volume_dict
        result = self.exports.getVolume(volume)
        self.assertEqual(volume_dict, result)
