import mock
import unittest

import kojihub
import kojihub.db


def get_qp_init(testcase):
    orig_qp_init = kojihub.db.QueryProcessor.__init__

    def my_qp_init(_query, *a, **kw):
        _query.execute = mock.MagicMock()
        _query.execute.return_value = testcase.qp_execute_return_value
        _query.execute.side_effect = testcase.qp_execute_side_effect
        _query.executeOne = mock.MagicMock()
        _query.executeOne.return_value = testcase.qp_execute_one_return_value
        _query.executeOne.side_effect = testcase.qp_execute_one_side_effect
        _query.singleValue = mock.MagicMock()
        _query.singleValue.return_value = testcase.qp_single_value_return_value
        _query.iterate = mock.MagicMock()
        _query.iterate.return_value = testcase.qp_iterate_return_value
        testcase.queries.append(_query)
        return orig_qp_init(_query, *a, **kw)

    return my_qp_init


class DBQueryTestCase(unittest.TestCase):

    def setUp(self):
        mock.patch.stopall()
        self.qp_execute_return_value = []
        self.qp_execute_side_effect = None
        self.qp_execute_one_return_value = []
        self.qp_execute_one_side_effect = None
        self.qp_single_value_return_value = None
        self.qp_iterate_return_value = None

        # patch init to catch queries regardless of how QP is imported
        new_init = get_qp_init(self)
        self.qp_init = mock.patch('kojihub.db.QueryProcessor.__init__', new=new_init).start()

        self.queries = []

    def tearDown(self):
        mock.patch.stopall()
        self.reset_query()

    def reset_query(self):
        del self.queries[:]

    def assertQueryEqual(self, query, **kwargs):
        for k, v in kwargs.items():
            self.assertEqual(getattr(query, k, None), v)

    def assertLastQueryEqual(self, **kwargs):
        query = self.queries[-1]
        self.assertQueryEqual(query, **kwargs)

    def assertQueriesEqual(self, arglist):
        for i, query in enumerate(self.queries):
            self.assertQueryEqual(query, **arglist[i])
