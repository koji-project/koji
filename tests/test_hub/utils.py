import mock
import unittest

import kojihub

QP = kojihub.QueryProcessor


class DBQueryTestCase(unittest.TestCase):

    def setUp(self):
        self.qp_execute_return_value = []
        self.qp_execute_side_effect = None
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                side_effect=self.get_query).start()
        self.queries = []

    def tearDown(self):
        mock.patch.stopall()
        self.reset_query()

    def reset_query(self):
        del self.queries[:]

    def get_query(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.execute.return_value = self.qp_execute_return_value
        query.execute.side_effect = self.qp_execute_side_effect
        self.queries.append(query)
        return query

    def assertQueryEqual(self, query, **kwargs):
        for k, v in kwargs.items():
            self.assertEqual(getattr(query, k, None), v)

    def assertLastQueryEqual(self, **kwargs):
        query = self.queries[-1]
        self.assertQueryEqual(query, **kwargs)

    def assertQueriesEqual(self, arglist):
        for i, query in enumerate(self.queries):
            self.assertQueryEqual(query, **arglist[i])

