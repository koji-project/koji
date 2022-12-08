import unittest

import mock

import koji
import kojihub


class TestGetGroupMembers(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.exports = kojihub.RootExports()

    def test_non_exist_group(self):
        group = 'test-group'
        self.get_user.return_value = []
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getGroupMembers(group)
        self.assertEqual("No such group: %s" % group, str(cm.exception))
