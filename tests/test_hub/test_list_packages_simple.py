import unittest
import kojihub
import mock

QP = kojihub.QueryProcessor


class TestListPackagesSimple(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
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

    def test_prefix_not_none(self):
        self.exports.listPackagesSimple('test-prefix')
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['package'])
        self.assertEqual(query.clauses, ["package.name ILIKE %(prefix)s || '%%'"])
        self.assertEqual(query.joins, None)

    def test_prefix_is_none(self):
        self.exports.listPackagesSimple()
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['package'])
        self.assertEqual(query.clauses, None)
        self.assertEqual(query.joins, None)
