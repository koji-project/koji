import mock

import kojihub
import kojihub.kojihub
from .utils import DBQueryTestCase


class TestListCGs(DBQueryTestCase):
    def setUp(self):
        super(TestListCGs, self).setUp()

    def tearDown(self):
        mock.patch.stopall()

    def test_valid(self):
        self.qp_iterate_return_value = [{'id': 1, 'name': 'cg_name_1', 'user_name': 'test-user'},
                                        {'id': 2, 'name': 'cg_name_2', 'user_name': 'test-user'}]
        expected_result = {'cg_name_1': {'id': 1, 'users': ['test-user']},
                           'cg_name_2': {'id': 2, 'users': ['test-user']}}
        rv = kojihub.list_cgs()
        self.assertEqual(rv, expected_result)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['cg_users'])
        self.assertEqual(query.columns, ['content_generator.id', 'content_generator.name',
                                         'users.name'])
        self.assertEqual(query.clauses, ['cg_users.active = TRUE'])
        self.assertEqual(query.joins, ['content_generator ON content_generator.id = '
                                       'cg_users.cg_id', 'users ON users.id = cg_users.user_id'])
        self.assertEqual(query.values, {})
