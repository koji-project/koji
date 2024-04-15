import mock
import unittest

import koji
import kojihub

UP = kojihub.UpdateProcessor


class TestSetUserStatus(unittest.TestCase):

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = self.update_execute
        self.updates.append(update)
        return update

    def setUp(self):
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.update_execute = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_wrong_status(self):
        status = 111
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.set_user_status(1, status)
        self.assertEqual(f'No such status: {status}', str(cm.exception))
        self.assertEqual(len(self.updates), 0)

    def test_status_is_setup(self):
        rv = kojihub.set_user_status({'status': 1}, 1)
        self.assertEqual(rv, None)
        self.assertEqual(len(self.updates), 0)

    def test_valid(self):
        self.update_execute.return_value = 1
        rv = kojihub.set_user_status({'status': 2, 'id': 123}, 1)
        self.assertEqual(rv, None)
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'users')
        self.assertEqual(update.values, {'user_id': 123})
        self.assertEqual(update.data, {'status': 1})
        self.assertEqual(update.rawdata, {})
        self.assertEqual(update.clauses, ['id = %(user_id)i'])

    def test_user_not_exist(self):
        self.update_execute.return_value = 0
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.set_user_status({'status': 2, 'id': 123}, 1)
        self.assertEqual('No such user ID: 123', str(cm.exception))
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'users')
        self.assertEqual(update.values, {'user_id': 123})
        self.assertEqual(update.data, {'status': 1})
        self.assertEqual(update.rawdata, {})
        self.assertEqual(update.clauses, ['id = %(user_id)i'])
