import unittest

import mock

import koji
import kojihub

GET_ARCHIVE_RV = {'id': 1, 'build_id': 2, 'type_id': 3,
                  'filename': 'somearchive.zip'}
GET_ARCHIVE_TYPE_RV = {'id': 3, 'name': 'zip'}
GET_BUILD_RV = {'id': 2, 'name': 'somebuild', 'version': '1.2.3',
                'release': '1.el6', 'volume_name': 'archive_vol'}


class TestListArchiveFiles(unittest.TestCase):
    def setUp(self):
        self.mm = mock.MagicMock()
        self.mm.get_image_build = mock.patch('kojihub.get_image_build',
                                             return_value=None).start()
        self.mm.get_win_build = mock.patch('kojihub.get_win_build',
                                           return_value=None).start()
        self.mm.get_maven_build = mock.patch('kojihub.get_maven_build',
                                             return_value=None).start()
        self.mm.get_build = mock.patch('kojihub.get_build',
                                       return_value=GET_BUILD_RV).start()
        self.mm.get_archive_type = mock.patch('kojihub.get_archive_type',
                                              return_value=GET_ARCHIVE_TYPE_RV).start()
        self.mm.get_archive = mock.patch('kojihub.get_archive',
                                         return_value=GET_ARCHIVE_RV).start()

    def tearDown(self):
        mock.patch.stopall()

    def test_simple(self):
        rv = kojihub.list_archive_files(1)
        self.mm.get_archive.assert_called_once_with(1, strict=True)
        self.mm.get_archive_type.assert_called_once_with(type_id=3,
                                                         strict=True)
        self.mm.get_build.assert_called_once_with(2, strict=True)
        self.mm.get_maven_build.assert_called_once_with(2)
        self.mm.get_win_build.assert_called_once_with(2)
        self.mm.get_image_build.assert_called_once_with(2)
        self.assertListEqual(rv, [])

    def test_simple_strict(self):
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.list_archive_files(1, strict=True)
        self.mm.get_archive.assert_called_once_with(1, strict=True)
        self.mm.get_archive_type.assert_called_once_with(type_id=3,
                                                         strict=True)
        self.mm.get_build.assert_called_once_with(2, strict=True)
        self.mm.get_maven_build.assert_called_once_with(2)
        self.mm.get_win_build.assert_called_once_with(2)
        self.mm.get_image_build.assert_called_once_with(2)
        self.assertEqual(cm.exception.args[0],
                         "Archive#1 doesn't contain any files")

    @mock.patch('kojihub.get_maven_archive',
                return_value={'archive_id': 1,
                              'group_id': 'gid',
                              'artifact_id': 'aid',
                              'version': '1.0.0'})
    @mock.patch('kojihub._get_zipfile_list', return_value=[{'archive_id': 1,
                                                            'name': 'file1',
                                                            'size': 4096,
                                                            'mtime': 1000},
                                                           {'archive_id': 1,
                                                            'name': 'file2',
                                                            'size': 512000,
                                                            'mtime': 103420},
                                                           ])
    def test_maven_archive(self, get_zipfile_list, get_maven_archive):
        self.mm.get_maven_build.return_value = {'build_id': 2,
                                                'group_id': 'gid',
                                                'artifact_id': 'aid',
                                                'version': '1.0.0'}
        rv = kojihub.list_archive_files(1)
        get_maven_archive.assert_called_once_with(1, strict=True)
        get_zipfile_list.assert_called_once_with(1,
                                                 '/mnt/koji/vol/archive_vol/packages'
                                                 '/somebuild/1.2.3/1.el6/maven/gid/aid/1.0.0/somearchive.zip')
        self.assertListEqual(rv, [
            {'archive_id': 1, 'mtime': 1000, 'name': 'file1', 'size': 4096},
            {'archive_id': 1, 'mtime': 103420, 'name': 'file2',
             'size': 512000}])

    @mock.patch('kojihub.get_win_archive', return_value={'archive_id': 1,
                                                         'relpath': 'rpath',
                                                         'platform': 'all',
                                                         'version': 'src'})
    @mock.patch('kojihub._get_zipfile_list', return_value=[{'archive_id': 1,
                                                            'name': 'file1',
                                                            'size': 4096,
                                                            'mtime': 1000},
                                                           {'archive_id': 1,
                                                            'name': 'file2',
                                                            'size': 512000,
                                                            'mtime': 103420},
                                                           ])
    def test_win_archive(self, get_zipfile_list, get_win_archive):
        self.mm.get_win_build.return_value = {'build_id': 2,
                                              'platform': 'all'}
        rv = kojihub.list_archive_files(1)
        get_win_archive.assert_called_once_with(1, strict=True)
        get_zipfile_list.assert_called_once_with(1,
                                                 '/mnt/koji/vol/archive_vol/packages'
                                                 '/somebuild/1.2.3/1.el6/win/rpath/somearchive.zip')
        self.assertListEqual(rv, [
            {'archive_id': 1, 'mtime': 1000, 'name': 'file1', 'size': 4096},
            {'archive_id': 1, 'mtime': 103420, 'name': 'file2',
             'size': 512000}])

    @mock.patch('kojihub.get_image_archive', return_value={'archive_id': 1,
                                                           'arch': 'noarch'})
    @mock.patch('kojihub._get_tarball_list', return_value=[{'archive_id': 1,
                                                            'name': 'file1',
                                                            'size': 4096,
                                                            'mtime': 1000,
                                                            'mode': '0755',
                                                            'user': 1000,
                                                            'group': 1000},
                                                           {'archive_id': 1,
                                                            'name': 'file2',
                                                            'size': 512000,
                                                            'mtime': 103420,
                                                            'mode': '0644',
                                                            'user': 1001,
                                                            'group': 1001}
                                                           ])
    def test_image_archive(self, get_tarball_list, get_image_archive):
        self.mm.get_archive_type.return_value = {'id': 3, 'name': 'tar'}
        self.mm.get_image_build.return_value = {'build_id': 2}
        rv = kojihub.list_archive_files(1, queryOpts={'countOnly': True})
        get_image_archive.assert_called_once_with(1, strict=True)
        get_tarball_list.assert_called_once_with(1,
                                                 '/mnt/koji/vol/archive_vol/packages'
                                                 '/somebuild/1.2.3/1.el6/images/somearchive.zip')
        self.assertEqual(rv, 2)
