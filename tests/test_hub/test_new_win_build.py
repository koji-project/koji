import unittest

import mock

import koji
import kojihub

IP = kojihub.InsertProcessor
UP = kojihub.UpdateProcessor


class TestNewWinBuild(unittest.TestCase):
    def setUp(self):
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.insert_execute = mock.MagicMock()
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.get_win_build = mock.patch('kojihub.kojihub.get_win_build').start()
        self.new_typed_build = mock.patch('kojihub.kojihub.new_typed_build').start()

        self.build_info = {
            'id': 100,
            'name': 'test_name',
            'version': 'test_version',
            'release': 'test_release',
            'epoch': 'test_epoch',
            'owner': 'test_owner',
            'extra': {'extra_key': 'extra_value'},
        }

    def tearDown(self):
        mock.patch.stopall()

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = self.insert_execute
        self.inserts.append(insert)
        return insert

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def test_empty_win_info(self):
        win_info = {}
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.new_win_build(self.build_info, win_info)
        self.assertEqual("Windows info is empty", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)
        self.get_win_build.assert_not_called()
        self.new_typed_build.assert_not_called()

    def test_win_info_without_platform(self):
        win_info = {
            'test-key': 'test-value'
        }
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.new_win_build(self.build_info, win_info)
        self.assertEqual("Windows info doesn't have mandatory platform key", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)
        self.get_win_build.assert_not_called()
        self.new_typed_build.assert_not_called()

    def test_wrong_format_win_info(self):
        win_info = 'test-win-info'
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.new_win_build(self.build_info, win_info)
        self.assertEqual('Invalid type for win_info: %s' % type(win_info), str(cm.exception))
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)
        self.get_win_build.assert_not_called()
        self.new_typed_build.assert_not_called()

    def test_valid_without_current_win_info(self):
        win_info = {
            'platform': 'test-platform'
        }
        self.get_win_build.return_value = None
        kojihub.new_win_build(self.build_info, win_info)
        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'win_builds')
        self.assertEqual(insert.data,
                         {'build_id': self.build_info['id'], 'platform': 'test-platform'})
        self.assertEqual(insert.rawdata, {})
        self.get_win_build.assert_called_once_with(self.build_info['id'], strict=False)
        self.new_typed_build.assert_called_once_with(self.build_info, 'win')

    def test_valid_with_current_win_info(self):
        win_info = {
            'platform': 'test-platform'
        }
        self.get_win_build.return_value = {'platform': 'test-platform-old'}
        kojihub.new_win_build(self.build_info, win_info)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'win_builds')
        self.assertEqual(update.values, {'build_id': self.build_info['id']})
        self.assertEqual(update.data, {'platform': 'test-platform'})
        self.assertEqual(update.rawdata, {})
        self.assertEqual(update.clauses, ['build_id=%(build_id)i'])
        self.get_win_build.assert_called_once_with(self.build_info['id'], strict=False)
        self.new_typed_build.assert_not_called()
