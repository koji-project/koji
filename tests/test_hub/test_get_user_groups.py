from unittest import mock

import koji
import kojihub
from .utils import DBQueryTestCase


class TestGetUserGroups(DBQueryTestCase):

    def setUp(self):
        super(TestGetUserGroups, self).setUp()
        self.exports = kojihub.RootExports()

        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context_db = mock.patch('kojihub.db.context').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_no_such_user(self):
        user = 'test-user'
        self.qp_execute_return_value = []
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getUserGroups(user)
        self.assertEqual(f"No such user: {user!r}", str(cm.exception))
        self.assertEqual(len(self.queries), 1)

    def test_valid(self):
        get_user = mock.patch('kojihub.kojihub.get_user').start()
        get_user.return_value = {'id': 23, 'usertype': 0}

        user = 'test-user'
        self.qp_execute_return_value = [{'group_id': 123, 'name': 'grp_123'},
                                        {'group_id': 456, 'name': 'grp_456'}]

        grps = self.exports.getUserGroups(user)

        get_user.assert_called_once_with(user, strict=True)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['user_groups'])
        self.assertEqual(query.joins, ['users ON group_id = users.id'])
        self.assertEqual(query.clauses, ['active IS TRUE',
                                         'user_id=%(user_id)i',
                                         'users.usertype=%(t_group)i'])
        self.assertEqual(query.values, {'t_group': 2,
                                        'user_id': 23})
        self.assertEqual(query.columns, ['group_id', 'name'])

        self.assertEqual(grps, [{'id': 123, 'name': 'grp_123'},
                                {'id': 456, 'name': 'grp_456'}])
