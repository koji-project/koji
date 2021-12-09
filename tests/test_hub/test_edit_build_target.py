import unittest

import mock

import koji
import kojihub


class TestEditBuildTarget(unittest.TestCase):

    def setUp(self):
        self.lookup_build_target = mock.patch('kojihub.lookup_build_target').start()
        self.verify_name_internal = mock.patch('kojihub.verify_name_internal').start()
        self.exports = kojihub.RootExports()

    def test_non_exist_build_target(self):
        session = kojihub.context.session = mock.MagicMock()
        session.assertPerm = mock.MagicMock()
        self.verify_name_internal.return_value = None
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

    def test_target_wrong_format(self):
        target_name = 'test-target'
        name = 'build-target-rename+'
        build_tag = 'tag'
        dest_tag = 'dest-tag'

        # name is longer as expected
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.editBuildTarget(target_name, name, build_tag, dest_tag)

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.editBuildTarget(target_name, name, build_tag, dest_tag)
