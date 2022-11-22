import mock
import unittest

import kojihub

QP = kojihub.QueryProcessor


class TestGetBuildType(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_execute = mock.MagicMock()
        self.get_build = mock.patch('kojihub.get_build').start()
        self.get_maven_build = mock.patch('kojihub.get_maven_build').start()
        self.get_win_build = mock.patch('kojihub.get_win_build').start()
        self.get_image_build = mock.patch('kojihub.get_image_build').start()

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = self.query_execute
        self.queries.append(query)
        return query

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

        self.query_execute.return_value = [['new_type']]

        ret = kojihub.get_build_type('mytestbuild-1-1', strict=True)
        assert ret == typeinfo
        self.get_build.assert_called_with('mytestbuild-1-1', strict=True)
        self.get_maven_build.assert_called_with(binfo['id'], strict=False)
        self.get_win_build.assert_called_with(binfo['id'], strict=False)
        self.get_image_build.assert_called_with(binfo['id'], strict=False)
