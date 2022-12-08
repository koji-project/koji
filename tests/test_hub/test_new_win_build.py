import unittest

import mock

import koji
import kojihub

IP = kojihub.InsertProcessor


class TestNewWinBuild(unittest.TestCase):
    def setUp(self):
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.insert_execute = mock.MagicMock()

        self.build_info = {
            'id': 100,
            'name': 'test_name',
            'version': 'test_version',
            'release': 'test_release',
            'epoch': 'test_epoch',
            'owner': 'test_owner',
            'extra': {'extra_key': 'extra_value'},
        }

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = self.insert_execute
        self.inserts.append(insert)
        return insert

    def test_empty_win_info(self):
        win_info = {}
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.new_win_build(self.build_info, win_info)
        self.assertEqual("Windows info is empty", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

    def test_win_info_without_platform(self):
        win_info = {
            'test-key': 'test-value'
        }
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.new_win_build(self.build_info, win_info)
        self.assertEqual("Windows info doesn't have mandatory platform key", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

    def test_wrong_format_win_info(self):
        win_info = 'test-win-info'
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.new_win_build(self.build_info, win_info)
        self.assertEqual('Invalid type for win_info: %s' % type(win_info), str(cm.exception))
        self.assertEqual(len(self.inserts), 0)
