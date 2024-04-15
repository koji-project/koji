import mock

import koji
import kojihub
from .utils import DBQueryTestCase


class TestGetBuild(DBQueryTestCase):

    def setUp(self):
        super(TestGetBuild, self).setUp()
        self.find_build_id = mock.patch('kojihub.kojihub.find_build_id').start()
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_non_exist_build_string_with_strict(self):
        build = 'build-1-23'
        self.find_build_id.side_effect = koji.GenericError('No such build: %s' % build)
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_build(build, strict=True)
        self.assertEqual('No such build: %s' % build, str(cm.exception))
        self.find_build_id.assert_called_once_with(build, strict=True)
        self.assertEqual(len(self.queries), 0)

    def test_non_exist_build_int_without_result_with_strict(self):
        build = 11
        self.find_build_id.return_value = build
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_build(build, strict=True)
        self.assertEqual('No such build: %s' % build, str(cm.exception))
        self.find_build_id.assert_called_once_with(build, strict=True)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['build'])
        self.assertEqual(query.clauses, ['build.id = %(buildID)i'])

    def test_non_exist_build_int_without_result_without_strict(self):
        build = 11
        self.find_build_id.return_value = build
        result = kojihub.get_build(build, strict=False)
        self.assertEqual(result, None)
        self.find_build_id.assert_called_once_with(build, strict=False)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['build'])
        self.assertEqual(query.clauses, ['build.id = %(buildID)i'])

    def test_non_exist_build_dict_with_strict(self):
        build = {
            'name': 'test_name',
            'version': 'test_version',
            'release': 'test_release',
        }
        self.find_build_id.side_effect = koji.GenericError('No such build: %s' % build['name'])
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_build(build, strict=True)
        self.assertEqual('No such build: %s' % build['name'], str(cm.exception))
        self.find_build_id.assert_called_once_with(build, strict=True)
        self.assertEqual(len(self.queries), 0)

    def test_build_none_exist_without_strict(self):
        build = 'build-1-23'
        self.find_build_id.return_value = None
        result = kojihub.get_build(build, strict=False)
        self.assertEqual(result, None)
        self.find_build_id.assert_called_once_with(build, strict=False)
        self.assertEqual(len(self.queries), 0)

    def test_result_with_cg_id_none(self):
        build = 11
        self.find_build_id.return_value = build
        self.qp_execute_one_return_value = {'cg_id': None}
        result = kojihub.get_build(build, strict=True)
        self.assertEqual(result, {'cg_id': None, 'cg_name': None})
        self.find_build_id.assert_called_once_with(build, strict=True)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['build'])
        self.assertEqual(query.clauses, ['build.id = %(buildID)i'])

    def test_result_with_cg_id(self):
        build = 11
        self.find_build_id.return_value = build
        self.lookup_name.return_value = {'name': 'cg_name'}
        self.qp_execute_one_return_value = {'cg_id': 1}
        result = kojihub.get_build(build, strict=True)
        self.assertEqual(result, {'cg_id': 1, 'cg_name': 'cg_name'})
        self.find_build_id.assert_called_once_with(build, strict=True)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['build'])
        self.assertEqual(query.clauses, ['build.id = %(buildID)i'])
