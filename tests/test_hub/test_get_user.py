import mock
import unittest

import koji
import kojihub
from .utils import DBQueryTestCase


class TestGetUser(DBQueryTestCase):

    def setUp(self):
        super(TestGetUser, self).setUp()
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.list_user_krb_principals = mock.patch(
            'kojihub.kojihub.list_user_krb_principals').start()

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

    def test_userinfo_dict_with_krbs(self):
        userinfo = {'id': 123456, 'name': 'test-user', 'krb_principal': 'test-krb@krb.com'}
        self.qp_execute_one_return_value = {'id': 123456, 'name': 'test-user',
                                            'status': 1, 'usertype': 1}
        self.list_user_krb_principals.return_value = 'test-krb@krb.com'
        result = kojihub.get_user(userinfo, krb_princs=True)
        self.assertEqual(result, {'id': 123456, 'krb_principals': 'test-krb@krb.com',
                                  'name': 'test-user', 'status': 1, 'usertype': 1})
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

    def test_userinfo_int_user_not_exist_and_strict(self):
        userinfo = {'id': 123456}
        self.qp_execute_one_return_value = {}
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_user(userinfo['id'], strict=True, krb_princs=False)
        self.assertEqual(f"No such user: {userinfo['id']}", str(cm.exception))
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        str(query)
        self.assertEqual(query.tables, ['users'])
        columns = ['id', 'name', 'status', 'usertype']
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(query.clauses, ['users.id = %(id)i'])
        self.assertEqual(query.joins, [])
        self.assertEqual(query.values, userinfo)


class TestGetUserByKrbPrincipal(unittest.TestCase):

    def setUp(self):
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()

    def tearDown(self):
        mock.patch.stopall()

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
