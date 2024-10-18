import unittest

from unittest import mock

import koji
import kojihub

QP = kojihub.QueryProcessor


class TestFindBuildId(unittest.TestCase):

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = mock.MagicMock()
        query.singleValue = self.query_singleValue
        self.queries.append(query)
        return query

    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_singleValue = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_non_exist_build_dict(self):
        build = {
            'name': 'test_name',
            'version': 'test_version',
            'release': 'test_release',
        }
        self.query_singleValue.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.find_build_id(build, strict=True)
        self.assertEqual("No such build: %s" % build, str(cm.exception))

    def test_invalid_argument(self):
        build = ['test-build']
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.find_build_id(build)
        self.assertEqual("Invalid type for argument: %s" % type(build), str(cm.exception))

    def test_build_dict_without_release(self):
        build = {
            'name': 'test_name',
            'version': 'test_version',
            'epoch': 'test_epoch',
            'owner': 'test_owner',
            'extra': {'extra_key': 'extra_value'},
        }
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.find_build_id(build, strict=True)
        self.assertEqual("did not provide name, version, and release", str(cm.exception))
