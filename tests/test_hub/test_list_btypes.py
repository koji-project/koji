import mock
import unittest

import kojihub

QP = kojihub.QueryProcessor


class TestListBTypes(unittest.TestCase):

    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                                         side_effect=self.get_query).start()
        self.queries = []
        self.exports = kojihub.RootExports()

    def tearDown(self):
        mock.patch.stopall()

    def get_query(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        self.queries.append(query)
        return query

    def test_list_btypes_default(self):
        kojihub.list_btypes()
        self.QueryProcessor.assert_called_once()

        args, kwargs = self.QueryProcessor.call_args
        self.assertEqual(args, ())
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['btype'])
        self.assertEqual(query.columns, ['id', 'name'])
        self.assertEqual(query.clauses, [])
        self.assertEqual(query.joins, None)

    def test_list_btypes_by_name(self):
        kojihub.list_btypes({'name': 'rpm'})
        self.QueryProcessor.assert_called_once()

        args, kwargs = self.QueryProcessor.call_args
        self.assertEqual(args, ())
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['btype'])
        self.assertEqual(query.columns, ['id', 'name'])
        self.assertEqual(query.clauses, ['btype.name = %(name)s'])
        self.assertEqual(query.values, {'name': 'rpm'})
        self.assertEqual(query.joins, None)

    def test_list_btypes_by_it_with_opts(self):
        kojihub.list_btypes({'id': 1}, {'order': 'id'})
        self.QueryProcessor.assert_called_once()

        args, kwargs = self.QueryProcessor.call_args
        self.assertEqual(args, ())
        query = self.queries[0]
        self.assertEqual(query.tables, ['btype'])
        self.assertEqual(query.columns, ['id', 'name'])
        self.assertEqual(query.clauses, ['btype.id = %(id)s'])
        self.assertEqual(query.values, {'id': 1})
        self.assertEqual(query.opts, {'order': 'id'})
        self.assertEqual(query.joins, None)
