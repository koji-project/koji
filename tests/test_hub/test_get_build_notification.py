import koji
import kojihub
from .utils import DBQueryTestCase


class TestGetBuildNotification(DBQueryTestCase):

    def setUp(self):
        super(TestGetBuildNotification, self).setUp()
        self.exports = kojihub.RootExports()

    def test_empty_result_with_strict(self):
        notif_id = 1
        self.qp_execute_one_return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getBuildNotification(notif_id, strict=True)
        self.assertEqual(f"No notification with ID {notif_id} found", str(cm.exception))
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['build_notifications'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['id = %(id)i'])
        self.assertEqual(query.columns,
                         ['email', 'id', 'package_id', 'success_only', 'tag_id', 'user_id'])

    def test_empty_result_without_strict(self):
        notif_id = 1
        self.qp_execute_one_return_value = None
        result = self.exports.getBuildNotification(notif_id, strict=False)
        self.assertEqual(result, None)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['build_notifications'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['id = %(id)i'])
        self.assertEqual(query.columns,
                         ['email', 'id', 'package_id', 'success_only', 'tag_id', 'user_id'])

    def test_valid_result(self):
        qp_result = {'id': 1, 'user_id': 2, 'package_id': 3, 'tag_id': 4, 'success_only': True,
                     'email': 'test-mail'}
        notif_id = 1
        self.qp_execute_one_return_value = qp_result
        result = self.exports.getBuildNotification(notif_id, strict=True)
        self.assertEqual(result, qp_result)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['build_notifications'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['id = %(id)i'])
        self.assertEqual(query.columns,
                         ['email', 'id', 'package_id', 'success_only', 'tag_id', 'user_id'])
