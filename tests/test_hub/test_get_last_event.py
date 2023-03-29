import koji
import kojihub
from .utils import DBQueryTestCase


class TestGetLastEvent(DBQueryTestCase):

    def setUp(self):
        super(TestGetLastEvent, self).setUp()
        self.exports = kojihub.RootExports()

    def test_wrong_type_before(self):
        before = '12345'
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getLastEvent(before)
        self.assertEqual("Invalid type for before: %s" % type(before), str(cm.exception))

    def test_valid(self):
        before = 123
        self.exports.getLastEvent(before)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['events'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ["date_part('epoch', time) < %(before)r"])
        self.assertEqual(query.values, {'before': 123})
        self.assertEqual(query.columns, ['id', "date_part('epoch', time)"])
