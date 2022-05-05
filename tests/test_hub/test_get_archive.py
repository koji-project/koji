import unittest
import mock

import koji
import kojihub


class TestGetArchive(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.list_archives = mock.patch('kojihub.list_archives').start()
        self.get_maven_archive = mock.patch('kojihub.get_maven_archive').start()
        self.get_win_archive = mock.patch('kojihub.get_win_archive').start()
        self.get_image_archive = mock.patch('kojihub.get_image_archive').start()

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

    def test_valid(self):
        archive_id = 1
        self.list_archives.return_value = [{'archive_id': 1, 'name': 'test-archive-1'}]
        self.get_maven_archive.return_value = {'archive_id': 2, 'name': 'test-archive-maven'}
        self.get_win_archive.return_value = {'archive_id': 3, 'name': 'test-archive-win'}
        self.get_image_archive.return_value = {'archive_id': 5, 'name': 'test-archive-image'}
        result = kojihub.get_archive(archive_id)
        self.assertEqual({'archive_id': 1, 'name': 'test-archive-image'}, result)

    def test_maven_archive_only(self):
        archive_id = 1
        self.list_archives.return_value = [{}]
        self.get_maven_archive.return_value = {'archive_id': 2, 'name': 'test-archive-maven'}
        self.get_win_archive.return_value = None
        self.get_image_archive.return_value = None
        result = kojihub.get_archive(archive_id)
        self.assertEqual({'name': 'test-archive-maven'}, result)

    def test_win_archive_only(self):
        archive_id = 1
        self.list_archives.return_value = [{}]
        self.get_maven_archive.return_value = None
        self.get_win_archive.return_value = {'archive_id': 3, 'name': 'test-archive-win'}
        self.get_image_archive.return_value = None
        result = kojihub.get_archive(archive_id)
        self.assertEqual({'name': 'test-archive-win'}, result)

    def test_image_archive_only(self):
        archive_id = 1
        self.list_archives.return_value = [{}]
        self.get_maven_archive.return_value = None
        self.get_win_archive.return_value = None
        self.get_image_archive.return_value = {'archive_id': 5, 'name': 'test-archive-image'}
        result = kojihub.get_archive(archive_id)
        self.assertEqual({'name': 'test-archive-image'}, result)

    def test_default_archive_only(self):
        archive_id = 1
        self.list_archives.return_value = [{'archive_id': 1, 'name': 'test-archive-1'}]
        self.get_maven_archive.return_value = None
        self.get_win_archive.return_value = None
        self.get_image_archive.return_value = None
        result = kojihub.get_archive(archive_id)
        self.assertEqual({'archive_id': 1, 'name': 'test-archive-1'}, result)
