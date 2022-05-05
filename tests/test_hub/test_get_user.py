import unittest

import mock

import koji
import kojihub

QP = kojihub.QueryProcessor


class TestGetUser(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.context').start()
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
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
            self.exports.getUser(userinfo)
        self.assertEqual(f"Invalid type for userInfo: {type(userinfo)}", str(cm.exception))

    def test_wrong_format_userid(self):
        userinfo = {'id': '123456'}
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getUser(userinfo)
        self.assertEqual(f"Invalid type for userid: {type(userinfo['id'])}", str(cm.exception))

    def test_wrong_format_username(self):
        userinfo = {'name': 57896}
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getUser(userinfo)
        self.assertEqual(f"Invalid type for username: {type(userinfo['name'])}", str(cm.exception))

    def test_wrong_format_krb_principal(self):
        userinfo = {'krb_principal': 57896}
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getUser(userinfo)
        self.assertEqual(f"Invalid type for krb_principal: {type(userinfo['krb_principal'])}",
                         str(cm.exception))

    def test_not_logged_user(self):
        self.context.session.user_id = None
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_user(userInfo=None)
        self.assertEqual("No user provided", str(cm.exception))

    def test_userinfo_string(self):
        userinfo = 'test-user'
        kojihub.get_user(userinfo, krb_princs=False)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        str(query)
        self.assertEqual(query.tables, ['users'])
        columns = ['id', 'name', 'status', 'usertype']
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(query.clauses, ['krb_principal = %(info)s OR name = %(info)s'])
        self.assertEqual(query.joins, ['LEFT JOIN user_krb_principals ON '
                                       'users.id = user_krb_principals.user_id'])
        self.assertEqual(query.values, {'info': userinfo})

    def test_userinfo_dict(self):
        userinfo = {'id': 123456, 'name': 'test-user', 'krb_principal': 'test-krb@krb.com'}
        kojihub.get_user(userinfo, krb_princs=False)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        str(query)
        self.assertEqual(query.tables, ['users'])
        columns = ['id', 'name', 'status', 'usertype']
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(query.clauses, ['user_krb_principals.krb_principal = %(krb_principal)s',
                                         'users.id = %(id)i', 'users.name = %(name)s'])
        self.assertEqual(query.joins, ['LEFT JOIN user_krb_principals ON '
                                       'users.id = user_krb_principals.user_id'])
        self.assertEqual(query.values, userinfo)


class TestGetUserByKrbPrincipal(unittest.TestCase):
    def setUp(self):
        self.get_user = mock.patch('kojihub.get_user').start()

    def test_wrong_type_krb_principal(self):
        krb_principal = ['test-user']
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_user_by_krb_principal(krb_principal)
        self.assertEqual(f"Invalid type for krb_principal: {type(krb_principal)}",
                         str(cm.exception))

    def test_krb_principal_none(self):
        krb_principal = None
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_user_by_krb_principal(krb_principal)
        self.assertEqual("No kerberos principal provided", str(cm.exception))

    def test_valid(self):
        krb_principal = 'test-user@test.org'
        user_info = {'id': 1, 'krb_principals': ['test-user@test.org'],
                     'name': 'test-user', 'status': 0, 'usertype': 0}
        self.get_user.return_value = user_info
        rv = kojihub.get_user_by_krb_principal(krb_principal)
        self.assertEqual(user_info, rv)
