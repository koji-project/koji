# coding: utf-8
import unittest

from unittest import mock

import koji
import kojihub

UP = kojihub.UpdateProcessor
IP = kojihub.InsertProcessor


class TestWriteInheritanceData(unittest.TestCase):

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        insert.make_create = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        update.make_revoke = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.maxDiff = None
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.read_inheritance_data = mock.patch('kojihub.kojihub.readInheritanceData').start()
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.tag_id = 5
        self.changes = {'parent_id': 10, 'priority': 7, 'maxdepth': None, 'intransitive': False,
                        'noconfig': False, 'pkg_filter': '', 'child_id': 5, 'is_update': True}

    def tearDown(self):
        mock.patch.stopall()

    def test_no_value_check_fields(self):
        changes = self.changes.copy()
        del changes['parent_id']
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.writeInheritanceData(self.tag_id, changes)
        self.assertEqual("No value for parent_id", str(cm.exception))
        self.read_inheritance_data.assert_not_called()
        self.get_tag.assert_not_called()
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    def test_valid(self):
        self.read_inheritance_data.return_value = [
            {'intransitive': False, 'maxdepth': None, 'name': 'test-tag', 'noconfig': False,
             'parent_id': 10, 'pkg_filter': '', 'priority': 4, 'child_id': 5}]
        self.get_tag.return_value = {'id': 10, 'name': 'parent_tag'}
        rv = kojihub.writeInheritanceData(self.tag_id, self.changes)
        self.assertEqual(rv, None)
        self.read_inheritance_data.assert_called_once_with(5)
        self.get_tag.assert_called_once_with(10, strict=True)
        self.assertEqual(len(self.inserts), 1)
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'tag_inheritance')
        self.assertEqual(update.clauses, ['tag_id=%(tag_id)s', 'parent_id = %(parent_id)s'])

        insert = self.inserts[0]
        self.assertEqual(insert.table, 'tag_inheritance')
        self.assertEqual(insert.data, {'parent_id': 10, 'priority': 7, 'maxdepth': None,
                                       'intransitive': False, 'noconfig': False,
                                       'pkg_filter': '', 'tag_id': 5})
        self.assertEqual(insert.rawdata, {})

    def test_delete_link(self):
        changes = self.changes.copy()
        changes['delete link'] = True
        self.read_inheritance_data.return_value = [
            {'intransitive': False, 'maxdepth': None, 'name': 'test-tag', 'noconfig': False,
             'parent_id': 10, 'pkg_filter': '', 'priority': 4, 'child_id': 5}]
        self.get_tag.return_value = {'id': 10, 'name': 'parent_tag'}
        rv = kojihub.writeInheritanceData(self.tag_id, changes)
        self.assertEqual(rv, None)
        self.read_inheritance_data.assert_called_once_with(5)
        self.get_tag.assert_called_once_with(10, strict=True)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'tag_inheritance')
        self.assertEqual(update.clauses, ['tag_id=%(tag_id)s', 'parent_id = %(parent_id)s'])

    def test_multiple_parent_with_the_same_priority(self):
        changes = self.changes.copy()
        changes = [changes, {'parent_id': 8, 'priority': 7, 'maxdepth': None,
                             'intransitive': False, 'noconfig': False, 'pkg_filter': '',
                             'child_id': 5, 'is_update': True}]
        self.read_inheritance_data.return_value = [
            {'intransitive': False, 'maxdepth': None, 'name': 'test-tag', 'noconfig': False,
             'parent_id': 10, 'pkg_filter': '', 'priority': 4, 'child_id': 5}]
        self.get_tag.return_value = {'id': 10, 'name': 'parent_tag'}
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.writeInheritanceData(self.tag_id, changes, clear=True)
        self.assertEqual(f"Multiple parent tags ([{changes[0]['parent_id']}, "
                         f"{changes[1]['parent_id']}]) cannot have the same priority value "
                         f"({changes[0]['priority']}) on child tag {changes[0]['child_id']}",
                         str(cm.exception))
        self.read_inheritance_data.assert_called_once_with(5)
        self.get_tag.assert_has_calls([mock.call(10, strict=True)], [mock.call(7, strict=True)])
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    def test_no_inheritance_changes(self):
        self.read_inheritance_data.return_value = [
            {'intransitive': False, 'maxdepth': None, 'name': 'test-tag', 'noconfig': False,
             'parent_id': 10, 'pkg_filter': '', 'priority': 7, 'child_id': 5}]
        self.get_tag.return_value = {'id': 10, 'name': 'parent_tag'}
        rv = kojihub.writeInheritanceData(self.tag_id, self.changes)
        self.assertEqual(rv, None)
        self.read_inheritance_data.assert_called_once_with(5)
        self.get_tag.assert_called_once_with(10, strict=True)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)
