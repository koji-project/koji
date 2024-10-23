from unittest import mock
import unittest

import koji
import kojihub

GET_ARCHIVE_RV = {'id': 1, 'build_id': 2, 'type_id': 3, 'btype': 'btype',
                  'filename': 'somearchive.zip'}
GET_ARCHIVE_TYPE_RV = {'id': 3, 'name': 'zip', 'compression_type': 'zip'}
GET_BUILD_RV = {'id': 2, 'name': 'somebuild', 'version': '1.2.3',
                'release': '1.el6', 'volume_name': 'archive_vol'}


class TestListArchiveFiles(unittest.TestCase):
    def setUp(self):
        self.mm = mock.MagicMock()
        # Note: the following mocks copy() the return value dict because some
        # of the tests modify it
        self.mm.get_build = mock.patch('kojihub.kojihub.get_build',
                                       return_value=GET_BUILD_RV.copy()).start()
        self.mm.get_archive_type = mock.patch('kojihub.kojihub.get_archive_type',
                                              return_value=GET_ARCHIVE_TYPE_RV.copy()).start()
        self.mm.get_archive = mock.patch('kojihub.kojihub.get_archive',
                                         return_value=GET_ARCHIVE_RV.copy()).start()
        self.mm.get_maven_archive = mock.patch('kojihub.kojihub.get_maven_archive').start()
        self.mm.get_win_archive = mock.patch('kojihub.kojihub.get_win_archive').start()
        self.mm.get_image_archive = mock.patch('kojihub.kojihub.get_image_archive').start()
        self.mm.get_zipfile_list = mock.patch('kojihub.kojihub._get_zipfile_list').start()
        self.mm.get_tarball_list = mock.patch('kojihub.kojihub._get_tarball_list').start()
        self.maven_archive = {'archive_id': 1, 'group_id': 'gid', 'artifact_id': 'aid',
                              'version': '1.0.0'}
        self.win_archive = {'archive_id': 1, 'relpath': 'rpath', 'platform': 'all',
                            'version': 'src'}
        self.image_archive = {'archive_id': 1, 'arch': 'noarch'}
        self.zipfile_list = [
            {'archive_id': 1, 'name': 'file1', 'size': 4096, 'mtime': 1000},
            {'archive_id': 1, 'name': 'file2', 'size': 512000, 'mtime': 103420},
        ]
        self.tarball_list = [
            {'archive_id': 1, 'name': 'file1', 'size': 4096, 'mtime': 1000, 'mode': '0755',
             'user': 1000, 'group': 1000},
            {'archive_id': 1, 'name': 'file2', 'size': 512000, 'mtime': 103420, 'mode': '0644',
             'user': 1001, 'group': 1001}
        ]
        self.archive_id = 1

    def tearDown(self):
        mock.patch.stopall()

    def test_simple(self):
        self.mm.get_zipfile_list.return_value = []
        rv = kojihub.list_archive_files(self.archive_id)
        self.mm.get_archive.assert_called_once_with(self.archive_id, strict=True)
        self.mm.get_archive_type.assert_called_once_with(type_id=3,
                                                         strict=True)
        self.mm.get_build.assert_called_once_with(2, strict=True)
        self.mm.get_zipfile_list.assert_called_once_with(
            1,
            '/mnt/koji/vol/archive_vol/packages/somebuild/1.2.3/1.el6/files/btype/somearchive.zip')
        self.mm.get_maven_archive.assert_not_called()
        self.mm.get_win_archive.assert_not_called()
        self.mm.get_image_archive.assert_not_called()
        self.mm.get_tarball_list.assert_not_called()
        self.assertListEqual(rv, [])

    def test_simple_strict_empty(self):
        self.mm.get_zipfile_list.return_value = []
        rv = kojihub.list_archive_files(self.archive_id, strict=True)
        self.mm.get_archive.assert_called_once_with(self.archive_id, strict=True)
        self.mm.get_archive_type.assert_called_once_with(type_id=3,
                                                         strict=True)
        self.mm.get_build.assert_called_once_with(2, strict=True)
        self.mm.get_zipfile_list.assert_called_once_with(
            1,
            '/mnt/koji/vol/archive_vol/packages/somebuild/1.2.3/1.el6/files/btype/somearchive.zip')
        self.mm.get_maven_archive.assert_not_called()
        self.mm.get_win_archive.assert_not_called()
        self.mm.get_image_archive.assert_not_called()
        self.mm.get_tarball_list.assert_not_called()
        self.assertListEqual(rv, [])

    def test_simple_strict_missing_btype(self):
        self.mm.get_archive.return_value['btype'] = None
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.list_archive_files(self.archive_id, strict=True)
        self.assertEqual(cm.exception.args[0],
                         f'Missing build type info for archive {self.archive_id}')
        self.mm.get_archive.assert_called_once_with(self.archive_id, strict=True)
        self.mm.get_archive_type.assert_called_once_with(type_id=3,
                                                         strict=True)
        self.mm.get_build.assert_called_once_with(2, strict=True)
        self.mm.get_maven_archive.assert_not_called()
        self.mm.get_win_archive.assert_not_called()
        self.mm.get_image_archive.assert_not_called()
        self.mm.get_zipfile_list.assert_not_called()
        self.mm.get_tarball_list.assert_not_called()

    def test_simple_strict_bad_archive_type_with_strict(self):
        self.mm.get_archive_type.return_value = {'id': 9, 'name': 'txt', 'compression_type': ''}
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.list_archive_files(self.archive_id, strict=True)
        self.assertEqual(cm.exception.args[0], "Unsupported archive type: txt")
        self.mm.get_archive.assert_called_once_with(self.archive_id, strict=True)
        self.mm.get_archive_type.assert_called_once_with(type_id=3,
                                                         strict=True)
        self.mm.get_build.assert_called_once_with(2, strict=True)
        self.mm.get_maven_archive.assert_not_called()
        self.mm.get_win_archive.assert_not_called()
        self.mm.get_image_archive.assert_not_called()
        self.mm.get_zipfile_list.assert_not_called()
        self.mm.get_tarball_list.assert_not_called()

    def test_simple_strict_bad_archive_type_without_strict(self):
        self.mm.get_archive_type.return_value = {'id': 9, 'name': 'txt', 'compression_type': ''}
        rv = kojihub.list_archive_files(1)
        self.mm.get_archive.assert_called_once_with(self.archive_id, strict=True)
        self.mm.get_archive_type.assert_called_once_with(type_id=3,
                                                         strict=True)
        self.mm.get_build.assert_called_once_with(2, strict=True)
        self.mm.get_win_archive.assert_not_called()
        self.mm.get_image_archive.assert_not_called()
        self.mm.get_zipfile_list.assert_not_called()
        self.mm.get_tarball_list.assert_not_called()
        self.mm.get_maven_archive.assert_not_called()
        self.assertListEqual(rv, [])

    def test_maven_archive(self):
        self.mm.get_maven_archive.return_value = self.maven_archive
        self.mm.get_zipfile_list.return_value = self.zipfile_list
        self.mm.get_archive.return_value['btype'] = 'maven'
        rv = kojihub.list_archive_files(1)
        self.mm.get_maven_archive.assert_called_once_with(1, strict=True)
        self.mm.get_zipfile_list.assert_called_once_with(
            1,
            '/mnt/koji/vol/archive_vol/packages/somebuild/1.2.3/1.el6/maven/gid/aid/'
            '1.0.0/somearchive.zip')
        self.mm.get_archive.assert_called_once_with(self.archive_id, strict=True)
        self.mm.get_archive_type.assert_called_once_with(type_id=3,
                                                         strict=True)
        self.mm.get_build.assert_called_once_with(2, strict=True)
        self.mm.get_win_archive.assert_not_called()
        self.mm.get_image_archive.assert_not_called()
        self.assertListEqual(rv, [
            {'archive_id': 1, 'mtime': 1000, 'name': 'file1', 'size': 4096},
            {'archive_id': 1, 'mtime': 103420, 'name': 'file2',
             'size': 512000}])

    def test_win_archive(self):
        self.mm.get_win_archive.return_value = self.win_archive
        self.mm.get_zipfile_list.return_value = self.zipfile_list
        self.mm.get_archive.return_value['btype'] = 'win'
        rv = kojihub.list_archive_files(1)
        self.mm.get_win_archive.assert_called_once_with(1, strict=True)
        self.mm.get_zipfile_list.assert_called_once_with(
            1,
            '/mnt/koji/vol/archive_vol/packages/somebuild/1.2.3/1.el6/win/rpath/somearchive.zip')
        self.mm.get_archive.assert_called_once_with(self.archive_id, strict=True)
        self.mm.get_archive_type.assert_called_once_with(type_id=3,
                                                         strict=True)
        self.mm.get_build.assert_called_once_with(2, strict=True)
        self.mm.get_image_archive.assert_not_called()
        self.mm.get_tarball_list.assert_not_called()
        self.mm.get_maven_archive.assert_not_called()
        self.assertListEqual(rv, [
            {'archive_id': 1, 'mtime': 1000, 'name': 'file1', 'size': 4096},
            {'archive_id': 1, 'mtime': 103420, 'name': 'file2',
             'size': 512000}])

    def test_image_archive(self):
        self.mm.get_image_archive.return_value = self.image_archive
        self.mm.get_tarball_list.return_value = self.tarball_list
        self.mm.get_archive_type.return_value = {'id': 3, 'name': 'tar', 'compression_type': 'tar'}
        self.mm.get_archive.return_value['btype'] = 'image'
        rv = kojihub.list_archive_files(1, queryOpts={'countOnly': True})
        self.mm.get_image_archive.assert_called_once_with(1, strict=True)
        self.mm.get_tarball_list.assert_called_once_with(
            1,
            '/mnt/koji/vol/archive_vol/packages/somebuild/1.2.3/1.el6/images/somearchive.zip')
        self.mm.get_archive.assert_called_once_with(self.archive_id, strict=True)
        self.mm.get_archive_type.assert_called_once_with(type_id=3,
                                                         strict=True)
        self.mm.get_build.assert_called_once_with(2, strict=True)
        self.mm.get_win_archive.assert_not_called()
        self.mm.get_zipfile_list.assert_not_called()
        self.mm.get_maven_archive.assert_not_called()
        self.assertEqual(rv, 2)
