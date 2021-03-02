import unittest

import mock

import koji
import kojihub


class TestListUserKrbPrincipals(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()

    def test_wrong_format_user_info(self):
        userinfo = ['test-user']
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.list_user_krb_principals(userinfo)
        self.assertEqual("Invalid type for user_info: %s" % type(userinfo), str(cm.exception))
