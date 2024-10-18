import unittest

from unittest import mock

import koji
import kojihub

QP = kojihub.QueryProcessor


class TestListUserKrbPrincipals(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        self.queries.append(query)
        return query

    def tearDown(self):
        mock.patch.stopall()

    def test_wrong_format_user_info(self):
        userinfo = ['test-user']
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.list_user_krb_principals(userinfo)
        self.assertEqual(f"Invalid type for user_info: {type(userinfo)}", str(cm.exception))

    def test_not_logged_user(self):
        self.context.session.user_id = None
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.list_user_krb_principals(user_info=None)
        self.assertEqual("No user provided", str(cm.exception))

    def test_userinfo_string(self):
        userinfo = 'test-user'
        kojihub.list_user_krb_principals(userinfo)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        str(query)
        self.assertEqual(query.tables, ['user_krb_principals'])
        columns = ['krb_principal']
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(query.clauses, ['name = %(info)s'])
        self.assertEqual(query.joins, ['users ON users.id = user_krb_principals.user_id'])
        self.assertEqual(query.values, {'info': userinfo})

    def test_userinfo_int(self):
        userinfo = 123
        kojihub.list_user_krb_principals(userinfo)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        str(query)
        self.assertEqual(query.tables, ['user_krb_principals'])
        columns = ['krb_principal']
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(query.clauses, ['user_id = %(info)i'])
        self.assertEqual(query.joins, [])
        self.assertEqual(query.values, {'info': userinfo})
