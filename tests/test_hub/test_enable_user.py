import unittest

import mock

import koji
import kojihub


class TestEnableUser(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.get_user = mock.patch('kojihub.get_user').start()

    def test_non_exist_user(self):
        username = 'test-user'
        self.get_user.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.enableUser(username)
        self.assertEqual("No such user: %s" % username, str(cm.exception))
