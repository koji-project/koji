import unittest

import mock

import koji
import kojihub


class TestDeleteBuildTarget(unittest.TestCase):

    def setUp(self):
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name').start()
        self.exports = kojihub.RootExports()

    def test_non_exist_target(self):
        build_target = 'build-target'
        self.lookup_name.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.deleteBuildTarget(build_target)
        self.assertEqual("No such build target: %s" % build_target, str(cm.exception))
