import unittest
from unittest import mock

import koji
import kojihub

QP = kojihub.QueryProcessor
IP = kojihub.InsertProcessor
UP = kojihub.UpdateProcessor


class TestCreateNotification(unittest.TestCase):
    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        self.queries.append(query)
        return query

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.opts = {
            'EmailDomain': 'test.domain.com',
            'NotifyOnSuccess': True,
        }
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.get_build_notifications = mock.patch('kojihub.kojihub.get_build_notifications').start()
        self.get_tag_id = mock.patch('kojihub.kojihub.get_tag_id').start()
        self.get_package_id = mock.patch('kojihub.kojihub.get_package_id').start()

        self.exports = kojihub.RootExports()
        self.exports.getLoggedInUser = mock.MagicMock()
        self.exports.getUser = mock.MagicMock()
        self.exports.hasPerm = mock.MagicMock()
        self.cursor = mock.MagicMock()
        self.user_id = 1
        self.package_id = 345
        self.tag_id = 345

    def tearDown(self):
        mock.patch.stopall()

    def test_createNotification(self):
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 1}
        self.exports.getUser.return_value = {'id': 2, 'name': 'username'}
        self.exports.hasPerm.return_value = True
        self.get_package_id.return_value = self.package_id
        self.get_tag_id.return_value = self.tag_id
        self.get_build_notifications.return_value = []

        r = self.exports.createNotification(
            self.user_id, self.package_id, self.tag_id, success_only)
        self.assertEqual(r, None)

        self.exports.getLoggedInUser.assert_called_once()
        self.exports.getUser.asssert_called_once_with(self.user_id)
        self.exports.hasPerm.asssert_called_once_with('admin')
        self.get_package_id.assert_called_once_with(self.package_id, strict=True)
        self.get_tag_id.assert_called_once_with(self.tag_id, strict=True)
        self.get_build_notifications.assert_called_once_with(2)
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'build_notifications')
        self.assertEqual(insert.data, {
            'package_id': self.package_id,
            'user_id': 2,
            'tag_id': self.tag_id,
            'success_only': success_only,
            'email': 'username@test.domain.com',
        })
        self.assertEqual(insert.rawdata, {})

    def test_createNotification_unauthentized(self):
        success_only = True
        self.exports.getLoggedInUser.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createNotification(
                self.user_id, self.package_id, self.tag_id, success_only)
        self.assertEqual('Not logged-in', str(cm.exception))

        self.assertEqual(len(self.inserts), 0)

    def test_createNotification_invalid_user(self):
        user_id = 2
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 1}
        self.exports.getUser.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createNotification(user_id, self.package_id, self.tag_id, success_only)
        self.assertEqual(f'No such user ID: {user_id}', str(cm.exception))

        self.assertEqual(len(self.inserts), 0)

    def test_createNotification_no_perm(self):
        user_id = 2
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 1, 'name': 'a'}
        self.exports.getUser.return_value = {'id': 2, 'name': 'b'}
        self.exports.hasPerm.return_value = False

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createNotification(user_id, self.package_id, self.tag_id, success_only)
        self.assertEqual('user a cannot create notifications for user b', str(cm.exception))

        self.assertEqual(len(self.inserts), 0)

    def test_createNotification_invalid_pkg(self):
        user_id = 2
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 2, 'name': 'a'}
        self.exports.getUser.return_value = {'id': 2, 'name': 'a'}
        self.get_package_id.side_effect = ValueError

        with self.assertRaises(ValueError):
            self.exports.createNotification(user_id, self.package_id, self.tag_id, success_only)

        self.assertEqual(len(self.inserts), 0)

    def test_createNotification_invalid_tag(self):
        user_id = 2
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 2, 'name': 'a'}
        self.exports.getUser.return_value = {'id': 2, 'name': 'a'}
        self.get_package_id.return_value = self.package_id
        self.get_tag_id.side_effect = ValueError

        with self.assertRaises(ValueError):
            self.exports.createNotification(user_id, self.package_id, self.tag_id, success_only)

        self.assertEqual(len(self.inserts), 0)

    def test_createNotification_exists(self):
        user_id = 2
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 2, 'name': 'a'}
        self.exports.getUser.return_value = {'id': 2, 'name': 'a'}
        self.get_package_id.return_value = self.package_id
        self.get_tag_id.return_value = self.tag_id
        self.get_build_notifications.return_value = [{
            'package_id': self.package_id,
            'tag_id': self.tag_id,
            'success_only': success_only,
        }]

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createNotification(user_id, self.package_id, self.tag_id, success_only)
        self.assertEqual('notification already exists', str(cm.exception))

        self.assertEqual(len(self.inserts), 0)
