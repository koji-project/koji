import unittest

import mock

import koji
import kojihub


class TestAddGroupMember(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()

    def test_non_exist_user(self):
        data = [{'id': 3,
                 'name': 'test-group',
                 'status': 0,
                 'usertype': 2,
                 'krb_principals': []},
                None,
                ]
        group = 'test-group'
        username = 'test-user'
        self.get_user.side_effect = data
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.addGroupMember(group, username)
        self.assertEqual("Not a user: %s" % username, str(cm.exception))

    def test_non_exist_group(self):
        data = [None,
                {'id': 1,
                 'krb_principals': [],
                 'name': 'test-user',
                 'status': 0,
                 'usertype': 0}
                ]
        group = 'test-group'
        username = 'test-user'
        self.get_user.side_effect = data
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.addGroupMember(group, username)
        self.assertEqual("Not a group: %s" % group, str(cm.exception))
