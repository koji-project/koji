import mock

import koji
import kojihub
from .utils import DBQueryTestCase


class TestGetGroupMembers(DBQueryTestCase):

    def setUp(self):
        super(TestGetGroupMembers, self).setUp()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_non_exist_group(self):
        group = 'test-group'
        self.get_user.return_value = []
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getGroupMembers(group)
        self.assertEqual("No such group: %s" % group, str(cm.exception))
        self.assertEqual(len(self.queries), 0)

    def test_valid(self):
        group = 'test-group'
        self.get_user.return_value = {'id': 23, 'usertype': 2}
        self.exports.getGroupMembers(group)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['user_groups'])
        self.assertEqual(query.joins, ['JOIN users ON user_groups.user_id = users.id',
                                       'LEFT JOIN user_krb_principals'
                                       ' ON users.id = user_krb_principals.user_id'])
        self.assertEqual(query.clauses, ['(active = TRUE)', 'group_id = %(group_id)i'])
        self.assertEqual(query.values, {'group_id': 23})
        self.assertEqual(query.columns, ['id', 'array_agg(krb_principal)', 'name', 'usertype'])
