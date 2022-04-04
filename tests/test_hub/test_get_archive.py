import unittest
import mock

import koji
import kojihub


class TestGetArchive(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.list_archives = mock.patch('kojihub.list_archives').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_get_archive_non_exist_archive_with_strict(self):
        archive_id = 1
        self.list_archives.return_value = []
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_archive(archive_id, strict=True)
        self.assertEqual(f"No such archive: {archive_id}", str(cm.exception))

    def test_get_archive_non_exist_archive_without_strict(self):
        archive_id = 1
        self.list_archives.return_value = []
        rv = kojihub.get_archive(archive_id)
        self.assertEqual(rv, None)
