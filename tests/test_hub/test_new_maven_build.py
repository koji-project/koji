import unittest

from unittest import mock

import koji
import kojihub

IP = kojihub.InsertProcessor


class TestNewMavenBuild(unittest.TestCase):
    def setUp(self):
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.insert_execute = mock.MagicMock()
        self.get_maven_build = mock.patch('kojihub.kojihub.get_maven_build').start()
        self.new_typed_build = mock.patch('kojihub.kojihub.new_typed_build').start()
        self.build_info = {
            'id': 100,
            'name': 'test_name',
            'version': 'test_version',
            'release': 'test_release',
            'epoch': 'test_epoch',
            'owner': 'test_owner',
            'build_id': 2,
        }

    def tearDown(self):
        mock.patch.stopall()

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = self.insert_execute
        self.inserts.append(insert)
        return insert

    def test_empty_maven_info(self):
        self.get_maven_build.return_value = None
        maven_info = {}
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.new_maven_build(self.build_info, maven_info)
        self.assertEqual("Maven info is empty", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)
        self.get_maven_build.assert_called_once_with(self.build_info)
        self.new_typed_build.assert_not_called()

    def test_maven_info_without_some_key(self):
        self.get_maven_build.return_value = None
        # maven_info without group_id
        maven_info = {
            'artifact_id': '99',
            'version': '33'
        }
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.new_maven_build(self.build_info, maven_info)
        self.assertEqual("Maven info doesn't have mandatory 'group_id' key", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

        # maven_info without artifact_id
        maven_info = {
            'group_id': '11',
            'version': '33'
        }
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.new_maven_build(self.build_info, maven_info)
        self.assertEqual("Maven info doesn't have mandatory 'artifact_id' key", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

        # maven_info without version
        maven_info = {
            'group_id': '11',
            'artifact_id': '99',
        }
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.new_maven_build(self.build_info, maven_info)
        self.assertEqual("Maven info doesn't have mandatory 'version' key", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

    def test_wrong_format_maven_info(self):
        maven_info = 'test-maven-info'
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.new_maven_build(self.build_info, maven_info)
        self.assertEqual('Invalid type for maven_info: %s' % type(maven_info), str(cm.exception))
        self.assertEqual(len(self.inserts), 0)
        self.get_maven_build.assert_not_called()
        self.new_typed_build.assert_not_called()

    def test_valid_without_current_maven_info(self):
        self.get_maven_build.return_value = None
        maven_info = {
            'artifact_id': '99',
            'version': '33',
            'build_id': 100,
            'group_id': 5,
        }
        kojihub.new_maven_build(self.build_info, maven_info)
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'maven_builds')
        self.assertEqual(insert.data, maven_info)
        self.assertEqual(insert.rawdata, {})
        self.get_maven_build.assert_called_once_with(self.build_info)
        self.new_typed_build.assert_called_once_with(self.build_info, 'maven')

    def test_mismatch_maven(self):
        maven_info_api = {
            'artifact_id': '99',
            'version': '33',
            'group_id': 5,
        }
        maven_info = {
            'artifact_id': '99',
            'version': '34',
            'group_id': 5,
        }
        self.get_maven_build.return_value = maven_info_api
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.new_maven_build(self.build_info, maven_info)
        self.assertEqual('version mismatch (current: 33, new: 34)', str(cm.exception))
        self.assertEqual(len(self.inserts), 0)
        self.get_maven_build.assert_called_once_with(self.build_info)
        self.new_typed_build.assert_not_called()
