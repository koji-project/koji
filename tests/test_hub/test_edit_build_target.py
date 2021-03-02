import unittest

import mock

import koji
import kojihub


class TestEditBuildTarget(unittest.TestCase):

    def setUp(self):
        self.lookup_build_target = mock.patch('kojihub.lookup_build_target').start()
        self.exports = kojihub.RootExports()

    def test_non_exist_build_target(self):
        session = kojihub.context.session = mock.MagicMock()
        session.assertPerm = mock.MagicMock()
        target_name = 'build-target'
        name = 'build-target-rename'
        build_tag = 'tag'
        dest_tag = 'dest-tag'
        self.lookup_build_target.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.editBuildTarget(target_name, name, build_tag, dest_tag)
        self.assertEqual("No such build target: %s" % target_name,
                         str(cm.exception))
        session.assertPerm.called_once_with('target')
