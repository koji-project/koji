import unittest

import mock

import koji
import kojihub

IP = kojihub.InsertProcessor


class TestCreateMavenBuild(unittest.TestCase):

    def setUp(self):
        self.get_build = mock.patch('kojihub.get_build').start()
        self.exports = kojihub.RootExports()
        self.session = mock.MagicMock()
        self.context = mock.patch('kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.insert_execute = mock.MagicMock()
        self.get_build_info = {
            'id': 100,
            'name': 'test_name',
            'version': 'test_version',
            'release': 'test_release',
            'epoch': 'test_epoch',
            'owner': 'test_owner',
            'build_id': 2,
        }
        self.build_info = 'test-build-11-12'

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = self.insert_execute
        self.inserts.append(insert)
        return insert

    def test_maven_info_empty_dict(self):
        maven_info = {}
        self.get_build.return_value = self.get_build_info
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createMavenBuild(self.build_info, maven_info)
        self.assertEqual("Maven info is empty", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

    def test_maven_info_without_some_key(self):
        # maven_info without group_id
        maven_info = {
            'artifact_id': '99',
            'version': '33'
        }
        self.get_build.return_value = self.get_build_info
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createMavenBuild(self.build_info, maven_info)
        self.assertEqual("Maven info doesn't have mandatory 'group_id' key", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

        # maven_info without artifact_id
        maven_info = {
            'group_id': '11',
            'version': '33'
        }
        self.get_build.return_value = self.get_build_info
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createMavenBuild(self.build_info, maven_info)
        self.assertEqual("Maven info doesn't have mandatory 'artifact_id' key", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

        # maven_info without version
        maven_info = {
            'group_id': '11',
            'artifact_id': '99',
        }
        self.get_build.return_value = self.get_build_info
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createMavenBuild(self.build_info, maven_info)
        self.assertEqual("Maven info doesn't have mandatory 'version' key", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

    def test_empty_wrong_format_maven_info(self):
        maven_info = 'maven-wrong-info'
        self.get_build.return_value = self.get_build_info
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createMavenBuild(self.build_info, maven_info)
        self.assertEqual('Invalid type for maven_info: %s' % type(maven_info), str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

    def test_empty_wrong_format_non_exist_build_info(self):
        maven_info = {
            'group_id': '11',
            'artifact_id': '99',
            'version': '33'
        }
        self.get_build.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createMavenBuild(self.build_info, maven_info)
        self.assertEqual(
            'Invalid type for build_info: %s' % type(self.build_info), str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

    def test_build_info_without_some_mandatory_key(self):
        maven_info = {
            'group_id': '11',
            'artifact_id': '99',
            'version': '33'
        }

        # build_info without name
        get_build_info = {
            'id': 100,
            'version': 'test_version',
            'release': 'test_release',
            'epoch': 'test_epoch',
        }
        self.get_build.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createMavenBuild(get_build_info, maven_info)
        self.assertEqual("Build info doesn't have mandatory 'name' key", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

        # build_info without version
        get_build_info = {
            'id': 100,
            'name': 'test_name',
            'release': 'test_release',
            'epoch': 'test_epoch',
        }
        self.get_build.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createMavenBuild(get_build_info, maven_info)
        self.assertEqual("Build info doesn't have mandatory 'version' key", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

        # build_info without release
        get_build_info = {
            'id': 100,
            'name': 'test_name',
            'version': 'test_version',
            'epoch': 'test_epoch',
        }
        self.get_build.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createMavenBuild(get_build_info, maven_info)
        self.assertEqual("Build info doesn't have mandatory 'release' key", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

        # build_info without epoch
        get_build_info = {
            'id': 100,
            'name': 'test_name',
            'version': 'test_version',
            'release': 'test_release',
        }
        self.get_build.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createMavenBuild(get_build_info, maven_info)
        self.assertEqual("Build info doesn't have mandatory 'epoch' key", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)
