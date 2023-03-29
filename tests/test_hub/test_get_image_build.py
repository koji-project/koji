import mock
import koji
import kojihub
from .utils import DBQueryTestCase


class TestGetImageBuild(DBQueryTestCase):

    def setUp(self):
        super(TestGetImageBuild, self).setUp()
        self.maxDiff = None
        self.find_build_id = mock.patch('kojihub.kojihub.find_build_id').start()

    def test_build_id_not_found(self):
        self.find_build_id.return_value = None
        result = kojihub.get_image_build('test-build.1-23.1')
        self.assertEqual(result, None)
        self.assertEqual(len(self.queries), 0)
        self.find_build_id.assert_called_once_with('test-build.1-23.1', strict=False)

    def test_valid(self):
        self.find_build_id.return_value = 123
        self.qp_execute_one_return_value = {'build_id': 123}
        kojihub.get_image_build('test-build.1-23.1')
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['image_builds'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['build_id = %(build_id)i'])
        self.assertEqual(query.values, {'build_id': 123})
        self.assertEqual(query.columns, ['build_id'])

        self.find_build_id.assert_called_once_with('test-build.1-23.1', strict=False)

    def test_without_result_without_strict(self):
        self.find_build_id.return_value = 123
        self.qp_execute_one_return_value = {}
        result = kojihub.get_image_build('test-build.1-23.1')
        self.assertEqual(result, {})
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['image_builds'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['build_id = %(build_id)i'])
        self.assertEqual(query.values, {'build_id': 123})
        self.assertEqual(query.columns, ['build_id'])

        self.find_build_id.assert_called_once_with('test-build.1-23.1', strict=False)

    def test_without_result_with_strict(self):
        self.find_build_id.return_value = 123
        self.qp_execute_one_return_value = {}
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.get_image_build('test-build.1-23.1', strict=True)
        self.assertEqual('no such image build: test-build.1-23.1', str(ex.exception))
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['image_builds'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['build_id = %(build_id)i'])
        self.assertEqual(query.values, {'build_id': 123})
        self.assertEqual(query.columns, ['build_id'])

        self.find_build_id.assert_called_once_with('test-build.1-23.1', strict=True)
