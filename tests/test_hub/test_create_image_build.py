import unittest

import mock

import koji
import kojihub

IP = kojihub.InsertProcessor


class TestCreateImageBuild(unittest.TestCase):

    def setUp(self):
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.exports = kojihub.RootExports()
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.insert_execute = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = self.insert_execute
        self.inserts.append(insert)
        return insert

    def test_empty_wrong_format_non_exist_build_info(self):
        build_info = 'test-build-11-12'
        self.get_build.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createImageBuild(build_info)
        self.assertEqual('Invalid type for build_info: %s' % type(build_info), str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

    def test_build_info_without_some_mandatory_key(self):
        # build_info without name
        get_build_info = {
            'id': 100,
            'version': 'test_version',
            'release': 'test_release',
            'epoch': 'test_epoch',
        }
        self.get_build.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createImageBuild(get_build_info)
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
            self.exports.createImageBuild(get_build_info)
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
            self.exports.createImageBuild(get_build_info)
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
            self.exports.createImageBuild(get_build_info)
        self.assertEqual("Build info doesn't have mandatory 'epoch' key", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)
