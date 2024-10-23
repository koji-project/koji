# coding: utf-8
import unittest

from unittest import mock

import koji
import kojihub


UP = kojihub.UpdateProcessor
DP = kojihub.DeleteProcessor


class TestCancelBuildRootExports(unittest.TestCase):

    def setUp(self):
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.cancel_build = mock.patch('kojihub.kojihub.cancel_build').start()
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_cancel_build_no_build(self):
        self.get_build.return_value = None
        rv = self.exports.cancelBuild(1)
        self.assertEqual(rv, False)
        self.get_build.assert_called_once_with(1, False)
        self.cancel_build.assert_not_called()

    def test_cancel_build_not_owner(self):
        self.context.session.user_id = 24
        self.context.session.hasPerm.return_value = False
        self.get_build.return_value = {'id': 1, 'owner_id': 23}
        with self.assertRaises(koji.ActionNotAllowed) as cm:
            self.exports.cancelBuild(1)
        self.assertEqual('Cannot cancel build, not owner', str(cm.exception))
        self.get_build.assert_called_once_with(1, False)
        self.cancel_build.assert_not_called()

    def test_cancel_build_valid(self):
        self.context.session.user_id = 23
        self.cancel_build.return_value = True
        self.get_build.return_value = {'id': 1, 'owner_id': 23}
        rv = self.exports.cancelBuild(1)
        self.assertEqual(rv, True)
        self.get_build.assert_called_once_with(1, False)
        self.cancel_build.assert_called_once_with(1)


class TestCancelBuildKojihub(unittest.TestCase):

    def setUp(self):
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.build_notification = mock.patch('kojihub.kojihub.build_notification').start()
        self.run_callbacks = mock.patch('koji.plugin.run_callbacks').start()
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.DeleteProcessor = mock.patch('kojihub.kojihub.DeleteProcessor',
                                          side_effect=self.getDelete).start()
        self.deletes = []

    def tearDown(self):
        mock.patch.stopall()

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def getDelete(self, *args, **kwargs):
        delete = DP(*args, **kwargs)
        delete.execute = mock.MagicMock()
        self.deletes.append(delete)
        return delete

    def test_cancel_build_not_st_building(self):
        self.get_build.return_value = {'id': 1, 'state': 2}
        rv = kojihub.cancel_build(1)
        self.assertEqual(rv, False)
        self.run_callbacks.assert_not_called()
        self.assertEqual(len(self.updates), 0)
        self.get_build.assert_called_once_with(1, strict=True)
        self.build_notification.assert_not_called()

    def test_cancel_build_not_st_canceled(self):
        self.get_build.side_effect = [{'id': 1, 'state': 0}, {'id': 1, 'state': 2}]
        rv = kojihub.cancel_build(1)
        self.assertEqual(rv, False)
        self.assertEqual(len(self.updates), 1)
        self.assertEqual(len(self.deletes), 0)
        update = self.updates[0]
        self.assertEqual(update.table, 'build')
        self.assertEqual(update.values, {'build_id': 1, 'st_building': 0})
        self.assertEqual(update.data, {'state': 4})
        self.assertEqual(update.rawdata, {'completion_time': 'NOW()'})
        self.assertEqual(update.clauses, ['id = %(build_id)i', 'state = %(st_building)i'])
        self.get_build.assert_has_calls([mock.call(1, strict=True), mock.call(1)])
        self.build_notification.assert_not_called()
        self.assertEqual(self.run_callbacks.call_count, 1)

    def test_cancel_build_valid(self):
        self.get_build.side_effect = [{'id': 1, 'state': 0}, {'id': 1, 'state': 4, 'task_id': 1},
                                      {'id': 1, 'state': 4, 'task_id': 1}]
        rv = kojihub.cancel_build(1, cancel_task=False)
        self.assertEqual(rv, True)

        self.assertEqual(len(self.updates), 1)
        self.assertEqual(len(self.deletes), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'build')
        self.assertEqual(update.values, {'build_id': 1, 'st_building': 0})
        self.assertEqual(update.data, {'state': 4})
        self.assertEqual(update.rawdata, {'completion_time': 'NOW()'})
        self.assertEqual(update.clauses, ['id = %(build_id)i', 'state = %(st_building)i'])

        delete = self.deletes[0]
        self.assertEqual(delete.table, 'build_reservations')
        self.assertEqual(delete.clauses, ['build_id = %(build_id)i'])
        self.assertEqual(delete.values, {'build_id': 1})

        self.get_build.assert_has_calls([mock.call(1, strict=True), mock.call(1),
                                         mock.call(1, strict=True)])
        self.build_notification.assert_called_once_with(1, 1)
        self.assertEqual(self.run_callbacks.call_count, 2)
