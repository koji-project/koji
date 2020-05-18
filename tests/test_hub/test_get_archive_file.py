import mock
import unittest

import koji
import kojihub

FILES = [{'archive_id': 1,
          'name': 'archive1.zip',
          'size': 1024},
         {'archive_id': 1,
          'name': 'archive2.jar',
          'size': 4096}]

EMPTY_FILES = []


class TestGetArchiveFile(unittest.TestCase):

    @mock.patch('kojihub.list_archive_files')
    def test_simple(self, list_archive_files):
        list_archive_files.return_value = FILES

        rv = kojihub.get_archive_file(1, 'archive1.zip')
        list_archive_files.assert_called_with(1, strict=False)
        self.assertEqual(rv, FILES[0])

        list_archive_files.reset_mock()
        rv = kojihub.get_archive_file(1, 'archive1.zip', strict=True)
        list_archive_files.assert_called_with(1, strict=True)
        self.assertEqual(rv, FILES[0])

    @mock.patch('kojihub.list_archive_files')
    def test_empty_files(self, list_archive_files):
        list_archive_files.return_value = EMPTY_FILES

        rv = kojihub.get_archive_file(1, 'archive1.zip')
        list_archive_files.assert_called_with(1, strict=False)
        self.assertIsNone(rv)

        list_archive_files.reset_mock()
        list_archive_files.side_effect = koji.GenericError('error message')

        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_archive_file(1, 'archive1.zip', strict=True)
        list_archive_files.assert_called_with(1, strict=True)
        self.assertEqual(cm.exception.args[0], 'error message')

    @mock.patch('kojihub.list_archive_files')
    def test_non_existing_file(self, list_archive_files):
        list_archive_files.return_value = FILES

        rv = kojihub.get_archive_file(1, 'archive3.xml')
        list_archive_files.assert_called_with(1, strict=False)
        self.assertEqual(rv, None)

        list_archive_files.reset_mock()

        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_archive_file(1, 'archive3.xml', strict=True)
        list_archive_files.assert_called_with(1, strict=True)
        self.assertEqual(cm.exception.args[0], 'No such file: archive3.xml in archive#1')
