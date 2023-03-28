import mock

import kojihub
from .utils import DBQueryTestCase


class TestGetBuildType(DBQueryTestCase):

    def setUp(self):
        super(TestGetBuildType, self).setUp()
        self.maxDiff = None
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.get_maven_build = mock.patch('kojihub.kojihub.get_maven_build').start()
        self.get_win_build = mock.patch('kojihub.kojihub.get_win_build').start()
        self.get_image_build = mock.patch('kojihub.kojihub.get_image_build').start()

    def test_no_build(self):
        self.get_build.return_value = None

        # strict on
        kojihub.get_build_type('mytestbuild-1-1', strict=True)
        self.assertEqual(len(self.queries), 0)
        self.get_build.assert_called_with('mytestbuild-1-1', strict=True)

    def test_has_build(self):
        typeinfo = {'maven': {'maven': 'foo'},
                    'win': {'win': 'foo'},
                    'image': {'image': 'foo'},
                    'new_type': {'bar': 42}}
        binfo = {'id': 1, 'extra': {'typeinfo': {'new_type': typeinfo['new_type']}}}
        self.get_build.return_value = binfo
        self.get_maven_build.return_value = typeinfo['maven']
        self.get_win_build.return_value = typeinfo['win']
        self.get_image_build.return_value = typeinfo['image']

        self.qp_execute_return_value = [['new_type']]

        ret = kojihub.get_build_type('mytestbuild-1-1', strict=True)
        assert ret == typeinfo
        self.get_build.assert_called_with('mytestbuild-1-1', strict=True)
        self.get_maven_build.assert_called_with(binfo['id'], strict=False)
        self.get_win_build.assert_called_with(binfo['id'], strict=False)
        self.get_image_build.assert_called_with(binfo['id'], strict=False)
