import mock
import unittest
import koji
import kojihub
import copy


class TestAddUserKrbPrincipal(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.verify_name_user = mock.patch('kojihub.kojihub.verify_name_user').start()
        self.get_user_by_krb_principal = mock.patch('kojihub.kojihub.get_user_by_krb_principal').start()
        self.username = 'testuser'
        self.krbprincipal = '%s@TEST.COM' % self.username
        self.userinfo = {'id': 1, 'name': self.username}

    def tearDown(self):
        mock.patch.stopall()

    def test_non_exist_user(self):
        self.get_user.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.RootExports().addUserKrbPrincipal(self.username, self.krbprincipal)

    def test_wrong_krbprincipal_format(self):
        krbprincipal = 'test-krbprincipal+'
        self.get_user.return_value = self.userinfo
        self.verify_name_user.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.RootExports().addUserKrbPrincipal(self.username, krbprincipal)

    def test_existing_krb(self):
        userinfo = copy.deepcopy(self.userinfo)
        userinfo['krb_principal'] = self.krbprincipal
        self.get_user.return_value = self.userinfo
        self.verify_name_user.return_value = None
        self.get_user_by_krb_principal.return_value = userinfo
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.RootExports().addUserKrbPrincipal(self.username, self.krbprincipal)
        self.assertEqual('user with this Kerberos principal already exists: %s'
                         % self.krbprincipal, str(ex.exception))
