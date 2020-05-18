
import os

import mock

import unittest
import koji
import kojihub


class TestGetRPMFile(unittest.TestCase):

    @mock.patch('kojihub.get_rpm')
    def test_getRPMFile_no_rpminfo(self, get_rpm):
        def mock_get_rpm(rpmID, strict=False):
            if strict:
                raise koji.GenericError('msg')
            else:
                return None

        get_rpm.side_effect = mock_get_rpm
        re = kojihub.RootExports().getRPMFile(1, 'filename')
        self.assertEquals(re, {})
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.RootExports().getRPMFile(1, 'filename', strict=True)
        self.assertEquals(cm.exception.args[0], 'msg')

    @mock.patch('kojihub.get_rpm', return_value={'id': 1, 'build_id': None})
    def test_getRPMFile_external_rpm(self, get_rpm):
        re = kojihub.RootExports().getRPMFile(1, 'filename')
        self.assertEquals(re, {})
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.RootExports().getRPMFile(1, 'filename', strict=True)
        self.assertEquals(cm.exception.args[0],
                          'Can not get RPM file,'
                          ' because RPM: 1 is not internal')

    @mock.patch('kojihub.get_rpm', return_value={'id': 1, 'build_id': 1})
    @mock.patch('kojihub.get_build', return_value={'id': 1})
    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('koji.pathinfo.rpm', return_value='fakerpmrelpath')
    @mock.patch('os.path.exists', return_value=False)
    def test_getRPMFile_no_rpmfile(self, ope, pr, pb, get_build, get_rpm):
        re = kojihub.RootExports().getRPMFile(1, 'filename')
        self.assertEquals(re, {})
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.RootExports().getRPMFile(1, 'filename', strict=True)
        self.assertEquals(cm.exception.args[0],
                          "RPM package file of 1 doesn't exist")

    @mock.patch('kojihub.get_rpm', return_value={'id': 1, 'build_id': 1})
    @mock.patch('kojihub.get_build')
    @mock.patch('koji.pathinfo')
    def test_getRPMFile(self, pi, build, rpm):
        pi.build.return_value = os.path.join(os.path.dirname(__file__),
                                             '../test_lib/data/rpms')
        pi.rpm.return_value = 'test-files-1-1.fc27.noarch.rpm'
        getRPMFile = kojihub.RootExports().getRPMFile
        res = getRPMFile(1, '/fileA')
        self.assertDictEqual(res, {'digest_algo': 'sha256',
                                   'user': 'root',
                                   'mtime': int(1535536271),
                                   'digest': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
                                   'size': 0,
                                   'group': 'root',
                                   'name': '/fileA',
                                   'rpm_id': 1,
                                   'flags': 0,
                                   'mode': int(0o100755),
                                   'md5': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'})
        res = getRPMFile(1, '/fileB')
        self.assertEquals(res, {})
        with self.assertRaises(koji.GenericError) as cm:
            res = getRPMFile(1, '/fileB', strict=True)
        self.assertEquals(cm.exception.args[0],
                          'No file: /fileB found in RPM: 1')
