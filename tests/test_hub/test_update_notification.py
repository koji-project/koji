import mock
import unittest

import koji
import kojihub

QP = kojihub.QueryProcessor
IP = kojihub.InsertProcessor
UP = kojihub.UpdateProcessor


class TestUpdateNotifications(unittest.TestCase):
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
        self.context = mock.patch('kojihub.context').start()
        self.context.opts = {
            'EmailDomain': 'test.domain.com',
            'NotifyOnSuccess': True,
        }

        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.get_build_notifications = mock.patch('kojihub.get_build_notifications').start()
        self.get_tag_id = mock.patch('kojihub.get_tag_id').start()
        self.get_package_id = mock.patch('kojihub.get_package_id').start()

        self.exports = kojihub.RootExports()
        self.exports.getLoggedInUser = mock.MagicMock()
        self.exports.hasPerm = mock.MagicMock()
        self.exports.getBuildNotification = mock.MagicMock()
        self.user_id = 1
        self.n_id = 5432
        self.package_id = 234
        self.tag_id = 345

    def tearDown(self):
        mock.patch.stopall()

    def test_updateNotification(self):
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 1}
        self.exports.hasPerm.return_value = True
        self.get_package_id.return_value = self.package_id
        self.get_tag_id.return_value = self.tag_id
        self.get_build_notifications.return_value = [{
            'tag_id': self.tag_id,
            'user_id': self.user_id,
            'package_id': self.package_id,
            'success_only': not success_only,
        }]
        self.exports.getBuildNotification.return_value = {'user_id': self.user_id}

        r = self.exports.updateNotification(self.n_id, self.package_id, self.tag_id, success_only)
        self.assertEqual(r, None)

        self.exports.getLoggedInUser.assert_called_once()
        self.exports.hasPerm.asssert_called_once_with('admin')
        self.get_package_id.assert_called_once_with(self.package_id, strict=True)
        self.get_tag_id.assert_called_once_with(self.tag_id, strict=True)
        self.get_build_notifications.assert_called_once_with(self.user_id)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 1)

    def test_updateNotification_not_logged(self):
        success_only = True
        self.exports.getLoggedInUser.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.updateNotification(self.n_id, self.package_id, self.tag_id, success_only)
        self.assertEqual('Not logged-in', str(cm.exception))

        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    def test_updateNotification_missing(self):
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 1}
        self.exports.getBuildNotification.side_effect = koji.GenericError

        with self.assertRaises(koji.GenericError):
            self.exports.updateNotification(self.n_id, self.package_id, self.tag_id, success_only)

        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    def test_updateNotification_no_perm(self):
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 132}
        self.exports.getBuildNotification.return_value = {'user_id': self.user_id}
        self.exports.hasPerm.return_value = False

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.updateNotification(self.n_id, self.package_id, self.tag_id, success_only)
        self.assertEqual(f'user 132 cannot update notifications for user {self.user_id}',
                         str(cm.exception))

        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    def test_updateNotification_exists(self):
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 1}
        self.exports.hasPerm.return_value = True
        self.get_package_id.return_value = self.package_id
        self.get_tag_id.return_value = self.tag_id
        self.get_build_notifications.return_value = [{
            'tag_id': self.tag_id,
            'user_id': self.user_id,
            'package_id': self.package_id,
            'success_only': success_only,
        }]
        self.exports.getBuildNotification.return_value = {'user_id': self.user_id}

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.updateNotification(self.n_id, self.package_id, self.tag_id, success_only)
        self.assertEqual('notification already exists', str(cm.exception))

        self.exports.getLoggedInUser.assert_called_once()
        self.exports.hasPerm.asssert_called_once_with('admin')
        self.get_package_id.assert_called_once_with(self.package_id, strict=True)
        self.get_tag_id.assert_called_once_with(self.tag_id, strict=True)
        self.get_build_notifications.assert_called_once_with(self.user_id)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)
