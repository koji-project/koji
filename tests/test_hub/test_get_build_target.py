import unittest

import mock

import koji
import kojihub


class TestGetBuildTarget(unittest.TestCase):

    def setUp(self):
        self.get_build_targets = mock.patch('kojihub.get_build_targets').start()
        self.exports = kojihub.RootExports()

    def test_non_exist_build_target(self):
        build_target = 'build-target'
        self.get_build_targets.return_value = []
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getBuildTarget(build_target, strict=True)
        self.assertEqual("No such build target: %s" % build_target, str(cm.exception))

    def test_wrong_type_build_target(self):
        build_target = {'info_key': 'info_value'}
        expected = "Invalid type for lookup: %s" % type(build_target)
        self.get_build_targets.side_effect = koji.GenericError(expected)
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getBuildTarget(build_target, strict=True)
        self.assertEqual(expected, str(cm.exception))
