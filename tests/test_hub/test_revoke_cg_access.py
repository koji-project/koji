# coding: utf-8
import unittest

import mock
import kojihub

UP = kojihub.UpdateProcessor


class TestRevokeCGAccess(unittest.TestCase):

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        update.make_revoke = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.maxDiff = None
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_valid(self):
        cg = {'id': 11, 'name': 'test-cg-name'}
        user = {'id': 123, 'name': 'testuser'}
        self.get_user.return_value = user
        self.lookup_name.return_value = cg
        kojihub.revoke_cg_access(user['name'], cg['name'])

        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'cg_users')
        self.assertEqual(update.values, {'user_id': user['id'], 'cg_id': cg['id']})
        self.assertEqual(update.data, {})
        self.assertEqual(update.rawdata, {})
        self.assertEqual(update.clauses, ["user_id = %(user_id)i", "cg_id = %(cg_id)i"])
        self.get_user.assert_called_once_with(user['name'], strict=True)
        self.lookup_name.assert_called_once_with('content_generator', cg['name'], strict=True)
