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

    def test_more_targets_without_strict(self):
        build_target = 'build-target'
        target_info = [{'build_tag': 123,
                        'build_tag_name': 'test-tag',
                        'dest_tag': 124,
                        'dest_tag_name': 'destination-test-tag',
                        'id': 1,
                        'name': 'test-build-target-1234'},
                       {'build_tag': 2,
                        'build_tag_name': 'test-tag-2',
                        'dest_tag': 3,
                        'dest_tag_name': 'destination-test-tag-2',
                        'id': 2,
                        'name': 'test-build-target-5678'}
                       ]
        self.get_build_targets.return_value = target_info
        rv = self.exports.getBuildTarget(build_target, strict=False)
        self.assertEqual(None, rv)

    def test_once_target(self):
        build_target = 'build-target-5678'
        target_info = [{'build_tag': 2,
                        'build_tag_name': 'test-tag-2',
                        'dest_tag': 3,
                        'dest_tag_name': 'destination-test-tag-2',
                        'id': 2,
                        'name': 'test-build-target-5678'}
                       ]
        self.get_build_targets.return_value = target_info
        rv = self.exports.getBuildTarget(build_target, strict=False)
        self.assertEqual(target_info[0], rv)
