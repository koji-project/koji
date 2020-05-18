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
        self.assertEquals(ret, "return value")

        args, kwargs = QueryProcessor.call_args
        self.assertEquals(args, ())
        qp = QP(**kwargs)
        self.assertEquals(qp.tables, ['btype'])
        self.assertEquals(qp.columns, ['id', 'name'])
        self.assertEquals(qp.clauses, [])
        self.assertEquals(qp.joins, None)

        QueryProcessor.reset_mock()

        # query by name
        query = QueryProcessor.return_value
        query.execute.return_value = "return value"
        ret = kojihub.list_btypes({'name': 'rpm'})
        QueryProcessor.assert_called_once()
        query.execute.assert_called_once()
        self.assertEquals(ret, "return value")

        args, kwargs = QueryProcessor.call_args
        self.assertEquals(args, ())
        qp = QP(**kwargs)
        self.assertEquals(qp.tables, ['btype'])
        self.assertEquals(qp.columns, ['id', 'name'])
        self.assertEquals(qp.clauses, ['btype.name = %(name)s'])
        self.assertEquals(qp.values, {'name': 'rpm'})
        self.assertEquals(qp.joins, None)

        QueryProcessor.reset_mock()

        # query by id, with opts
        query = QueryProcessor.return_value
        query.execute.return_value = "return value"
        ret = kojihub.list_btypes({'id': 1}, {'order': 'id'})
        QueryProcessor.assert_called_once()
        query.execute.assert_called_once()
        self.assertEquals(ret, "return value")

        args, kwargs = QueryProcessor.call_args
        self.assertEquals(args, ())
        qp = QP(**kwargs)
        self.assertEquals(qp.tables, ['btype'])
        self.assertEquals(qp.columns, ['id', 'name'])
        self.assertEquals(qp.clauses, ['btype.id = %(id)s'])
        self.assertEquals(qp.values, {'id': 1})
        self.assertEquals(qp.opts, {'order': 'id'})
        self.assertEquals(qp.joins, None)

        QueryProcessor.reset_mock()

        # query by name
