import mock
import unittest

import koji
import kojihub

QP = kojihub.QueryProcessor
IP = kojihub.InsertProcessor
UP = kojihub.UpdateProcessor


class TestDeleteNotificationsBlocks(unittest.TestCase):
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
        self.get_user = mock.patch('kojihub.get_user').start()
        self._dml = mock.patch('kojihub._dml').start()

        self.exports = kojihub.RootExports()
        self.exports.getLoggedInUser = mock.MagicMock()
        self.exports.hasPerm = mock.MagicMock()
        self.exports.getBuildNotificationBlock = mock.MagicMock()
        self.user_id = 752
        self.n_id = 543

    def tearDown(self):
        mock.patch.stopall()

    def test_deleteNotificationBlock(self):
        self.exports.getBuildNotificationBlock.return_value = {'user_id': self.user_id}

        self.exports.deleteNotificationBlock(self.n_id)

        self.exports.getBuildNotificationBlock.assert_called_once_with(self.n_id, strict=True)
        self.exports.getLoggedInUser.assert_called_once_with()
        self._dml.assert_called_once()

    def test_deleteNotificationBlock_missing(self):
        self.exports.getBuildNotificationBlock.side_effect = koji.GenericError

        with self.assertRaises(koji.GenericError):
            self.exports.deleteNotificationBlock(self.n_id)

        self.exports.getBuildNotificationBlock.assert_called_once_with(self.n_id, strict=True)

    def test_deleteNotificationBlock_not_logged(self):
        self.exports.getBuildNotificationBlock.return_value = {'user_id': self.user_id}
        self.exports.getLoggedInUser.return_value = None
        # self.set_queries = ([
        #    [{'user_id': 5, 'email': 'owner_name@%s' % self.context.opts['EmailDomain']}],
        # ])

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.deleteNotificationBlock(self.n_id)
        self.assertEqual('Not logged-in', str(cm.exception))

        self.exports.getBuildNotificationBlock.assert_called_once_with(self.n_id, strict=True)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.queries), 0)

    def test_deleteNotificationBlock_no_perm2(self):
        self.exports.getBuildNotificationBlock.return_value = {'user_id': self.user_id}
        self.exports.getLoggedInUser.return_value = {'id': 1}
        self.exports.hasPerm.return_value = False

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.deleteNotificationBlock(self.n_id)
        self.assertEqual(f'user 1 cannot delete notification blocks for user {self.user_id}',
                         str(cm.exception))

        self.exports.getBuildNotificationBlock.assert_called_once_with(self.n_id, strict=True)
        self._dml.assert_not_called()
