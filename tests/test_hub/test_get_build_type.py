import mock
import unittest

import kojihub


class TestGetBuildType(unittest.TestCase):

    @mock.patch('kojihub.get_build')
    @mock.patch('kojihub.QueryProcessor')
    def test_no_build(self, QueryProcessor, get_build):
        get_build.return_value = None

        # strict on
        kojihub.get_build_type('mytestbuild-1-1', strict=True)
        QueryProcessor.assert_not_called()
        get_build.assert_called_with('mytestbuild-1-1', strict=True)


    @mock.patch('kojihub.get_maven_build')
    @mock.patch('kojihub.get_win_build')
    @mock.patch('kojihub.get_image_build')
    @mock.patch('kojihub.get_build')
    @mock.patch('kojihub.QueryProcessor')
    def test_has_build(self, QueryProcessor, get_build, get_image_build,
                get_win_build, get_maven_build):
        typeinfo = {'maven': {'maven': 'foo'},
                    'win': {'win': 'foo'},
                    'image': {'image': 'foo'},
                    'new_type': {'bar': 42}}
        binfo = {'id' : 1, 'extra' : {'typeinfo': {'new_type': typeinfo['new_type']}}}
        get_build.return_value = binfo
        get_maven_build.return_value = typeinfo['maven']
        get_win_build.return_value = typeinfo['win']
        get_image_build.return_value = typeinfo['image']

        query = QueryProcessor.return_value
        query.execute.return_value = [['new_type']]

        ret = kojihub.get_build_type('mytestbuild-1-1', strict=True)
        assert ret == typeinfo
        get_build.assert_called_with('mytestbuild-1-1', strict=True)
        get_maven_build.assert_called_with(binfo['id'], strict=False)
        get_win_build.assert_called_with(binfo['id'], strict=False)
        get_image_build.assert_called_with(binfo['id'], strict=False)
