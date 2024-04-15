import unittest

import mock

import koji
import kojihub

IP = kojihub.InsertProcessor


class TestCreateWinBuild(unittest.TestCase):

    def setUp(self):
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.exports = kojihub.RootExports()
        self.session = mock.MagicMock()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
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
            'extra': {'extra_key': 'extra_value'},
            'build_id': 2,
        }
        self.build_info = 'test-build-11-12'

    def tearDown(self):
        mock.patch.stopall()

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = self.insert_execute
        self.inserts.append(insert)
        return insert

    def test_win_info_empty_dict(self):
        win_info = {}
        self.get_build.return_value = self.get_build_info
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createWinBuild(self.build_info, win_info)
        self.assertEqual("Windows info is empty", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

    def test_win_info_without_platform(self):
        win_info = {
            'test-key': 'test-value'
        }
        self.get_build.return_value = self.get_build_info
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createWinBuild(self.build_info, win_info)
        self.assertEqual("Windows info doesn't have mandatory platform key", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

    def test_empty_wrong_format_win_info(self):
        win_info = 'platform'
        self.get_build.return_value = self.get_build_info
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createWinBuild(self.build_info, win_info)
        self.assertEqual('Invalid type for win_info: %s' % type(win_info), str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

    def test_empty_wrong_format_non_exist_build_info(self):
        win_info = {
            'platform': 'test-value'
        }
        self.get_build.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createWinBuild(self.build_info, win_info)
        self.assertEqual(
            'Invalid type for build_info: %s' % type(self.build_info), str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

    def test_build_info_without_some_mandatory_key(self):
        win_info = {
            'platform': 'test-value'
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
            self.exports.createWinBuild(get_build_info, win_info)
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
            self.exports.createWinBuild(get_build_info, win_info)
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
            self.exports.createWinBuild(get_build_info, win_info)
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
            self.exports.createWinBuild(get_build_info, win_info)
        self.assertEqual("Build info doesn't have mandatory 'epoch' key", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)
