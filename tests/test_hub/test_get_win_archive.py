import kojihub
from .utils import DBQueryTestCase


class TestGetWinArchive(DBQueryTestCase):

    def setUp(self):
        super(TestGetWinArchive, self).setUp()
        self.maxDiff = None

    def test_valid(self):
        kojihub.get_win_archive(123)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['win_archives'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['archive_id = %(archive_id)i'])
        self.assertEqual(query.values, {'archive_id': 123})
        self.assertEqual(query.columns, ['archive_id', 'flags', 'platforms', 'relpath'])
