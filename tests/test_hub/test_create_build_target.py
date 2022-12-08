# coding: utf-8
import unittest

import mock

import koji
import kojihub


class TestCreateBuildTarget(unittest.TestCase):

    def setUp(self):
        self.get_build_targets = mock.patch('kojihub.kojihub.get_build_targets').start()
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.verify_name_internal = mock.patch('kojihub.kojihub.verify_name_internal').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()
        self.tag_name = 'test-tag'
        self.destination_tag_name = 'dest-test-tag'
        self.target_name = 'test_target'
        self.build_target_info = {
            'build_tag': 2,
            'build_tag_name': self.tag_name,
            'dest_tag': 3,
            'dest_tag_name': self.destination_tag_name,
            'id': 1,
            'name': self.target_name
        }
        self.tag_info = {'arches': '',
                         'extra': {},
                         'id': 1,
                         'locked': False,
                         'maven_include_all': False,
                         'maven_support': False,
                         'name': self.tag_name,
                         'perm': None,
                         'perm_id': None}

    def tearDown(self):
        mock.patch.stopall()

    def test_target_wrong_format(self):
        target_name = 'test-target+'

        # name is longer as expected
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.create_build_target(target_name, self.tag_name, self.destination_tag_name)

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.create_build_target(target_name, self.tag_name, self.destination_tag_name)

    def test_target_exists(self):
        self.get_build_targets.return_value = self.build_target_info
        self.verify_name_internal.return_value = None
        expected = "A build target with the name '%s' already exists" % self.target_name
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.create_build_target(self.target_name, self.tag_name, self.destination_tag_name)
        self.assertEqual(expected, str(cm.exception))

    def test_tag_not_exists(self):
        self.get_build_targets.return_value = None
        self.verify_name_internal.return_value = None
        self.get_tag.return_value = None
        expected = "build tag '%s' does not exist" % self.tag_name
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.create_build_target(self.target_name, self.tag_name, self.destination_tag_name)
        self.assertEqual(expected, str(cm.exception))

    def test_dest_tag_not_exists(self):
        self.get_build_targets.return_value = None
        self.verify_name_internal.return_value = None
        self.get_tag.side_effect = [self.tag_info, None]
        expected = "destination tag '%s' does not exist" % self.destination_tag_name
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.create_build_target(self.target_name, self.tag_name, self.destination_tag_name)
        self.assertEqual(expected, str(cm.exception))
