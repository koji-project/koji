from unittest import mock
import unittest
import koji
import kojihub


class TestDownloadTaskOutput(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.exports.getVolume = mock.MagicMock()
        self.task_id = 1
        self.filename = 'test-file'
        self.volumename = 'test-volume'

    def tearDown(self):
        mock.patch.stopall()

    def test_size_wrong_type(self):
        size = 'test-size'
        with self.assertRaises(koji.ParameterError) as cm:
            self.exports.downloadTaskOutput(self.task_id, self.filename, size=size)
        self.assertEqual(f"Invalid type for value '{size}': {type(size)}, "
                         f"expected type <class 'int'>", str(cm.exception))

    def test_volume_non_exist_wrong_type(self):
        self.exports.getVolume.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.downloadTaskOutput(self.task_id, self.filename, volume=self.volumename)

    def test_filename_wrong_format(self):
        filename = '../test-file'
        volumeinfo = {'id': 1, 'name': self.volumename}
        self.exports.getVolume.return_value = volumeinfo
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.downloadTaskOutput(self.task_id, filename, volume=self.volumename)
        self.assertEqual(f"Invalid file name: {filename}", str(cm.exception))
