import mock
import unittest

import kojihub

QP = kojihub.QueryProcessor


class TestListBTypes(unittest.TestCase):

    @mock.patch('kojihub.QueryProcessor')
    def test_list_btypes(self, QueryProcessor):

        # default query
        query = QueryProcessor.return_value
        query.execute.return_value = "return value"
        ret = kojihub.list_btypes()
        QueryProcessor.assert_called_once()
        query.execute.assert_called_once()
        self.assertEqual(ret, "return value")

        args, kwargs = QueryProcessor.call_args
        self.assertEqual(args, ())
        qp = QP(**kwargs)
        self.assertEqual(qp.tables, ['btype'])
        self.assertEqual(qp.columns, ['id', 'name'])
        self.assertEqual(qp.clauses, [])
        self.assertEqual(qp.joins, None)

        QueryProcessor.reset_mock()

        # query by name
        query = QueryProcessor.return_value
        query.execute.return_value = "return value"
        ret = kojihub.list_btypes({'name': 'rpm'})
        QueryProcessor.assert_called_once()
        query.execute.assert_called_once()
        self.assertEqual(ret, "return value")

        args, kwargs = QueryProcessor.call_args
        self.assertEqual(args, ())
        qp = QP(**kwargs)
        self.assertEqual(qp.tables, ['btype'])
        self.assertEqual(qp.columns, ['id', 'name'])
        self.assertEqual(qp.clauses, ['btype.name = %(name)s'])
        self.assertEqual(qp.values, {'name': 'rpm'})
        self.assertEqual(qp.joins, None)

        QueryProcessor.reset_mock()

        # query by id, with opts
        query = QueryProcessor.return_value
        query.execute.return_value = "return value"
        ret = kojihub.list_btypes({'id': 1}, {'order': 'id'})
        QueryProcessor.assert_called_once()
        query.execute.assert_called_once()
        self.assertEqual(ret, "return value")

        args, kwargs = QueryProcessor.call_args
        self.assertEqual(args, ())
        qp = QP(**kwargs)
        self.assertEqual(qp.tables, ['btype'])
        self.assertEqual(qp.columns, ['id', 'name'])
        self.assertEqual(qp.clauses, ['btype.id = %(id)s'])
        self.assertEqual(qp.values, {'id': 1})
        self.assertEqual(qp.opts, {'order': 'id'})
        self.assertEqual(qp.joins, None)

        QueryProcessor.reset_mock()

        # query by name
