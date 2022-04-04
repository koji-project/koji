import unittest

import mock

import koji
import kojihub


QP = kojihub.QueryProcessor
IP = kojihub.InsertProcessor


class TestLookupName(unittest.TestCase):

    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_executeOne = mock.MagicMock()
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.nextval = mock.patch('kojihub.nextval').start()
        self.context = mock.patch('kojihub.context').start()

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.executeOne = self.query_executeOne
        self.queries.append(query)
        return query

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def tearDown(self):
        mock.patch.stopall()

    def test_wrong_lookup_type(self):
        bad_values = [
            {'foo': 'missing id and name fields'},
            {'id': 'not a valid int'},
            ['something'],
            set(),
        ]
        for value in bad_values:
            with self.assertRaises(koji.GenericError) as cm:
                kojihub.lookup_name('mytable', value)
            self.assertEqual(f'Invalid name or id value: {value}', str(cm.exception))
        self.assertEqual(len(self.queries), 0)
        self.assertEqual(len(self.inserts), 0)

    def test_query_by_name(self):
        kojihub.lookup_name('some_table', 'herbert')
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        clauses = ['(some_table.name = %(some_table_name)s)']
        values = {'some_table_name': 'herbert'}
        self.assertEqual(query.tables, ['some_table'])
        self.assertEqual(query.joins, None)
        self.assertEqual(set(query.clauses), set(clauses))
        self.assertEqual(query.values, values)
        self.assertEqual(len(self.inserts), 0)

    def test_query_by_id(self):
        kojihub.lookup_name('some_table', 12345)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        clauses = ['(some_table.id = %(some_table_id)s)']
        values = {'some_table_id': 12345}
        self.assertEqual(query.tables, ['some_table'])
        self.assertEqual(query.joins, None)
        self.assertEqual(set(query.clauses), set(clauses))
        self.assertEqual(query.values, values)
        self.assertEqual(len(self.inserts), 0)

    def test_query_by_dict(self):
        kojihub.lookup_name('some_table', {'id': 12345, 'name': 'whatever'})
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        clauses = ['(some_table.id = %(some_table_id)s)']
        values = {'some_table_id': 12345}
        self.assertEqual(query.tables, ['some_table'])
        self.assertEqual(query.joins, None)
        self.assertEqual(set(query.clauses), set(clauses))
        self.assertEqual(query.values, values)
        self.assertEqual(len(self.inserts), 0)

    def test_query_by_dict_with_name(self):
        kojihub.lookup_name('some_table', {'name': 'whatever'})
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        clauses = ['(some_table.name = %(some_table_name)s)']
        values = {'some_table_name': 'whatever'}
        self.assertEqual(query.tables, ['some_table'])
        self.assertEqual(query.joins, None)
        self.assertEqual(set(query.clauses), set(clauses))
        self.assertEqual(query.values, values)
        self.assertEqual(len(self.inserts), 0)

    def test_lookup_name_no_match(self):
        self.query_executeOne.return_value = None
        result = kojihub.lookup_name('package', 'python')
        self.assertEqual(len(self.queries), 1)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(result, None)

    def test_lookup_name_strict(self):
        self.query_executeOne.return_value = None
        with self.assertRaises(koji.GenericError):
            kojihub.lookup_name('package', 'python', strict=True)
        self.assertEqual(len(self.queries), 1)
        self.assertEqual(len(self.inserts), 0)

    def test_lookup_name_create(self):
        self.query_executeOne.return_value = None
        self.nextval.return_value = 999
        result = kojihub.lookup_name('package', 'python', create=True)
        self.assertEqual(len(self.queries), 1)
        self.assertEqual(len(self.inserts), 1)
        expected = {'id': 999, 'name': 'python'}
        self.assertEqual(result, expected)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'package')
        self.assertEqual(insert.data, expected)
        self.assertEqual(insert.rawdata, {})
        insert.execute.assert_called_once()

    def test_lookup_name_create_wrong_type(self):
        self.query_executeOne.return_value = None
        bad_values = [
            {'id': 100},
            100
        ]
        for value in bad_values:
            with self.assertRaises(koji.GenericError) as cm:
                kojihub.lookup_name('package', value, create=True)
            self.assertEqual('Name must be a string', str(cm.exception))
        self.assertEqual(len(self.inserts), 0)
        self.nextval.assert_not_called()
