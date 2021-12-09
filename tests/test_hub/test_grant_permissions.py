import unittest

import mock

import koji
import kojihub


class TestGrantPermission(unittest.TestCase):

    def setUp(self):
        self.verify_name_internal = mock.patch('kojihub.verify_name_internal').start()
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()
        self.user_name = 'test_user'

    def test_grant_permission_wrong_format(self):
        perms_name = 'test-perms+'

        # name is longer as expected
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.grantPermission(self.user_name, perms_name, create=True)

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.grantPermission(self.user_name, perms_name, create=True)
