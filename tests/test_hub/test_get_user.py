import unittest

import mock

import koji
import kojihub


class TestGetUser(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()

    def test_wrong_format_user_info(self):
        userinfo = ['test-user']
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getUser(userinfo)
        self.assertEqual("Invalid type for userInfo: %s" % type(userinfo), str(cm.exception))

    def test_wrong_format_userid(self):
        userinfo = {'id': '123456'}
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getUser(userinfo)
        self.assertEqual("Invalid type for userid: %s" % type(userinfo['id']), str(cm.exception))

    def test_wrong_format_username(self):
        userinfo = {'name': 57896}
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getUser(userinfo)
        self.assertEqual("Invalid type for username: %s" % type(userinfo['name']),
                         str(cm.exception))

    def test_wrong_format_krb_principal(self):
        userinfo = {'krb_principal': 57896}
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getUser(userinfo)
        self.assertEqual("Invalid type for krb_principal: %s" % type(userinfo['krb_principal']),
                         str(cm.exception))


class TestGetUserByKrbPrincipal(unittest.TestCase):
    def setUp(self):
        self.get_user = mock.patch('kojihub.get_user').start()

    def test_wrong_type_krb_principal(self):
        krb_principal = ['test-user']
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_user_by_krb_principal(krb_principal)
        self.assertEqual("Invalid type for krb_principal: %s" % type(krb_principal),
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
