import koji
import kojihub
from unittest import mock
from .utils import DBQueryTestCase


class TestGetArchiveType(DBQueryTestCase):
    def setUp(self):
        super(TestGetArchiveType, self).setUp()
        self.maxDiff = None
        self.archive_info = {'id': 1, 'name': 'archive-type-1',
                             'description': 'archive-desc', 'extensions': 'ext',
                             'compression_type': 'cmptype'}

    @mock.patch('kojihub.kojihub._get_archive_type_by_name')
    @mock.patch('kojihub.kojihub._get_archive_type_by_id')
    def test_get_archive_wrong_type_filename(
            self, get_archive_type_by_id, get_archive_type_by_name):
        filename = ['test-filename']
        with self.assertRaises(koji.ParameterError) as ex:
            kojihub.get_archive_type(filename=filename)
        self.assertEqual(f"Invalid type for value '{filename}': {type(filename)}, "
                         f"expected type <class 'str'>", str(ex.exception))
        self.assertEqual(len(self.queries), 0)
        get_archive_type_by_name.assert_not_called()
        get_archive_type_by_id.assert_not_called()

    @mock.patch('kojihub.kojihub._get_archive_type_by_name')
    @mock.patch('kojihub.kojihub._get_archive_type_by_id')
    def test_get_archive_without_opt(self, get_archive_type_by_id, get_archive_type_by_name):
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.get_archive_type()
        self.assertEqual("one of filename, type_name, or type_id must be specified",
                         str(ex.exception))
        self.assertEqual(len(self.queries), 0)
        get_archive_type_by_name.assert_not_called()
        get_archive_type_by_id.assert_not_called()

    @mock.patch('kojihub.kojihub._get_archive_type_by_name')
    @mock.patch('kojihub.kojihub._get_archive_type_by_id')
    def test_get_archive_type_id(self, get_archive_type_by_id, get_archive_type_by_name):
        get_archive_type_by_id.return_value = self.archive_info
        kojihub.get_archive_type(type_id=1)
        self.assertEqual(len(self.queries), 0)
        get_archive_type_by_name.assert_not_called()
        get_archive_type_by_id.assert_called_once_with(1, False)

    @mock.patch('kojihub.kojihub._get_archive_type_by_name')
    @mock.patch('kojihub.kojihub._get_archive_type_by_id')
    def test_get_archive_type_name(self, get_archive_type_by_id, get_archive_type_by_name):
        get_archive_type_by_name.return_value = self.archive_info
        kojihub.get_archive_type(type_name='archive-type-1')
        self.assertEqual(len(self.queries), 0)
        get_archive_type_by_name.assert_called_once_with('archive-type-1', False)
        get_archive_type_by_id.assert_not_called()

    @mock.patch('kojihub.kojihub._get_archive_type_by_name')
    @mock.patch('kojihub.kojihub._get_archive_type_by_id')
    def test_get_archive_more_files_extension(
            self, get_archive_type_by_id, get_archive_type_by_name):
        archive_info = [{'id': 1, 'name': 'archive-type-1', 'extensions': 'ext'},
                        {'id': 2, 'name': 'archive-type-2', 'extensions': 'ext'}]
        filename = 'test-filename.ext'
        self.qp_execute_return_value = archive_info
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.get_archive_type(filename=filename)
        self.assertEqual("multiple matches for file extension: ext", str(ex.exception))

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archivetypes'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['extensions ~* %(pattern)s'])
        self.assertEqual(query.columns,
                         ['compression_type', 'description', 'extensions', 'id', 'name'])
        get_archive_type_by_name.assert_not_called()
        get_archive_type_by_id.assert_not_called()

    @mock.patch('kojihub.kojihub._get_archive_type_by_name')
    @mock.patch('kojihub.kojihub._get_archive_type_by_id')
    def test_get_archive_no_extensions_with_strict(
            self, get_archive_type_by_id, get_archive_type_by_name):
        archive_info = []
        filename = 'test-filename.ext'
        self.qp_execute_return_value = archive_info
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.get_archive_type(filename=filename, strict=True)
        self.assertEqual(f'unsupported file extension: {filename}', str(ex.exception))

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archivetypes'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['extensions ~* %(pattern)s'])
        self.assertEqual(query.columns,
                         ['compression_type', 'description', 'extensions', 'id', 'name'])
        get_archive_type_by_name.assert_not_called()
        get_archive_type_by_id.assert_not_called()

    @mock.patch('kojihub.kojihub._get_archive_type_by_name')
    @mock.patch('kojihub.kojihub._get_archive_type_by_id')
    def test_get_archive_no_extensions_without_strict(
            self, get_archive_type_by_id, get_archive_type_by_name):
        archive_info = []
        filename = 'test-filename.ext'
        self.qp_execute_return_value = archive_info
        result = kojihub.get_archive_type(filename=filename, strict=False)
        self.assertEqual(result, None)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archivetypes'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['extensions ~* %(pattern)s'])
        self.assertEqual(query.columns,
                         ['compression_type', 'description', 'extensions', 'id', 'name'])
        get_archive_type_by_name.assert_not_called()
        get_archive_type_by_id.assert_not_called()

    @mock.patch('kojihub.kojihub._get_archive_type_by_name')
    @mock.patch('kojihub.kojihub._get_archive_type_by_id')
    def test_get_archive_valid(self, get_archive_type_by_id, get_archive_type_by_name):
        filename = 'test-filename.ext'
        self.qp_execute_return_value = [self.archive_info]
        result = kojihub.get_archive_type(filename=filename)
        self.assertEqual(result, self.archive_info)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archivetypes'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['extensions ~* %(pattern)s'])
        self.assertEqual(query.columns,
                         ['compression_type', 'description', 'extensions', 'id', 'name'])
        get_archive_type_by_name.assert_not_called()
        get_archive_type_by_id.assert_not_called()

    def test_get_archive_type_by_id_empty_without_strict(self):
        self.qp_execute_one_return_value = None
        result = kojihub._get_archive_type_by_id(1, False)
        self.assertEqual(result, None)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archivetypes'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['id = %(type_id)i'])
        self.assertEqual(query.columns,
                         ['compression_type', 'description', 'extensions', 'id', 'name'])
        self.assertEqual(query.values, {'type_id': 1})

    def test_get_archive_type_by_id_empty_with_strict(self):
        self.qp_execute_one_side_effect = koji.GenericError('query returned no rows')
        with self.assertRaises(koji.GenericError) as ex:
            kojihub._get_archive_type_by_id(1, True)
        self.assertEqual('query returned no rows', str(ex.exception))
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archivetypes'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['id = %(type_id)i'])
        self.assertEqual(query.columns,
                         ['compression_type', 'description', 'extensions', 'id', 'name'])
        self.assertEqual(query.values, {'type_id': 1})

    def test_get_archive_type_by_name_without_strict(self):
        self.qp_execute_one_return_value = None
        result = kojihub._get_archive_type_by_name('archive-type', False)
        self.assertEqual(result, None)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archivetypes'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['name = %(name)s'])
        self.assertEqual(query.columns,
                         ['compression_type', 'description', 'extensions', 'id', 'name'])
        self.assertEqual(query.values, {'name': 'archive-type'})

    def test_get_archive_type_by_name_with_strict(self):
        self.qp_execute_one_side_effect = koji.GenericError('query returned no rows')
        with self.assertRaises(koji.GenericError) as ex:
            kojihub._get_archive_type_by_name('archive-type', True)
        self.assertEqual('query returned no rows', str(ex.exception))
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['archivetypes'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['name = %(name)s'])
        self.assertEqual(query.columns,
                         ['compression_type', 'description', 'extensions', 'id', 'name'])
        self.assertEqual(query.values, {'name': 'archive-type'})
