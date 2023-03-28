import kojihub
from .utils import DBQueryTestCase


class TestGetImageArchive(DBQueryTestCase):

    def setUp(self):
        super(TestGetImageArchive, self).setUp()
        self.maxDiff = None

    def test_not_exist_image_archive(self):
        self.qp_execute_one_return_value = {}
        result = kojihub.get_image_archive(123)
        self.assertEqual(result, None)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['image_archives'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['archive_id = %(archive_id)i'])
        self.assertEqual(query.values, {'archive_id': 123})
        self.assertEqual(query.columns, ['arch', 'archive_id'])

    def test_valid(self):
        self.qp_execute_one_side_effect = [{'archive_id': 123, 'arch': 'arch'},
                                           {'rpm_id': 1}]
        result = kojihub.get_image_archive(123)
        self.assertEqual(result, {'archive_id': 123, 'arch': 'arch', 'rootid': True})
        self.assertEqual(len(self.queries), 2)
        query = self.queries[0]
        self.assertEqual(query.tables, ['image_archives'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['archive_id = %(archive_id)i'])
        self.assertEqual(query.values, {'archive_id': 123})
        self.assertEqual(query.columns, ['arch', 'archive_id'])

        query = self.queries[1]
        self.assertEqual(query.tables, ['archive_rpm_components'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['archive_id = %(archive_id)i'])
        self.assertEqual(query.values, {'archive_id': 123})
        self.assertEqual(query.columns, ['rpm_id'])
