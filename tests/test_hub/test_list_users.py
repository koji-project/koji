import unittest

import mock

import koji
import kojihub

QP = kojihub.QueryProcessor


class TestListUsers(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.exports = kojihub.RootExports()
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.get_perm_id = mock.patch('kojihub.kojihub.get_perm_id').start()

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = mock.MagicMock()
        self.queries.append(query)
        return query

    def test_valid_default(self):
        self.exports.listUsers()

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['users'])
        self.assertEqual(query.joins, [
            'LEFT JOIN user_krb_principals ON users.id = user_krb_principals.user_id'])
        self.assertEqual(query.clauses, ['usertype IN %(userType)s'])

    def test_valid_userType_none_with_perm_and_prefix(self):
        self.exports.listUsers(userType=None, perm='admin', prefix='koji')

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['users'])
        self.assertEqual(query.joins, [
            'LEFT JOIN user_perms ON users.id = user_perms.user_id',
            'LEFT JOIN user_krb_principals ON users.id = user_krb_principals.user_id'])
        self.assertEqual(query.clauses, [
            'user_perms.active AND user_perms.perm_id = %(perm_id)s',
            "users.name ilike %(prefix)s || '%%'",
        ])

    def test_valid_userType_none_with_perm_inherited_perm_and_prefix(self):
        self.exports.listUsers(userType=None, perm='admin', prefix='koji', inherited_perm=True)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['users'])
        self.assertEqual(query.joins, [
            'LEFT JOIN user_groups ON user_id = users.id AND user_groups.active IS TRUE',
            'LEFT JOIN user_perms ON users.id = user_perms.user_id '
                'OR group_id = user_perms.user_id',
            'LEFT JOIN user_krb_principals ON users.id = user_krb_principals.user_id'])
        self.assertEqual(query.clauses, [
            'user_perms.active AND user_perms.perm_id = %(perm_id)s',
            "users.name ilike %(prefix)s || '%%'",
        ])

    def test_inherited_perm_without_perm(self):
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.listUsers(userType=None, inherited_perm=True)
        self.assertEqual('inherited_perm option must be used with perm option',
                         str(cm.exception))
        self.assertEqual(len(self.queries), 0)

    def test_wrong_queryopts_group(self):
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.listUsers(queryOpts={'group': 'test-column'})
        self.assertEqual('queryOpts.group is not available for this API', str(cm.exception))
        self.assertEqual(len(self.queries), 0)

    def test_usertype_not_int_or_none(self):
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.listUsers(userType=[1])
        self.assertEqual('userType must be integer or None', str(cm.exception))
        self.assertEqual(len(self.queries), 0)
