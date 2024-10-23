import unittest
import koji
import kojihub
from unittest import mock


class TestBuildImageIndirection(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.exports = kojihub.RootExports()
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.hasPerm = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_priority_without_admin(self):
        priority = -10
        self.context.session.assertPerm.side_effect = None
        self.context.session.hasPerm.return_value = False
        with self.assertRaises(koji.ActionNotAllowed) as cm:
            self.exports.buildImageIndirection(priority=priority)
        self.assertEqual("only admins may create high-priority tasks", str(cm.exception))

    def test_opts_without_expected_keys(self):
        priority = 10
        opts = {}
        self.context.session.assertPerm.side_effect = None
        with self.assertRaises(koji.ActionNotAllowed) as cm:
            self.exports.buildImageIndirection(opts=opts, priority=priority)
        self.assertEqual("Non-scratch builds must provide url for the indirection template",
                         str(cm.exception))
