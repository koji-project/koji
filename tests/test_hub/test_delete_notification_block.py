import mock
import unittest

import koji
import kojihub

DP = kojihub.DeleteProcessor


class TestDeleteNotificationsBlocks(unittest.TestCase):
    def getDelete(self, *args, **kwargs):
        delete = DP(*args, **kwargs)
        delete.execute = mock.MagicMock()
        self.deletes.append(delete)
        return delete

    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        self.context.opts = {
            'EmailDomain': 'test.domain.com',
            'NotifyOnSuccess': True,
        }

        self.DeleteProcessor = mock.patch('kojihub.DeleteProcessor',
                                          side_effect=self.getDelete).start()
        self.deletes = []
        self.get_user = mock.patch('kojihub.get_user').start()

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
        self.assertEqual(len(self.deletes), 1)
        delete = self.deletes[0]
        self.assertEqual(delete.table, 'build_notifications_block')
        self.assertEqual(delete.clauses, ['id=%(id)i'])

        self.exports.getBuildNotificationBlock.assert_called_once_with(self.n_id, strict=True)
        self.exports.getLoggedInUser.assert_called_once_with()

    def test_deleteNotificationBlock_missing(self):
        self.exports.getBuildNotificationBlock.side_effect = koji.GenericError

        with self.assertRaises(koji.GenericError):
            self.exports.deleteNotificationBlock(self.n_id)
        self.assertEqual(len(self.deletes), 0)

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
        self.assertEqual(len(self.deletes), 0)

        self.exports.getBuildNotificationBlock.assert_called_once_with(self.n_id, strict=True)

    def test_deleteNotificationBlock_no_perm2(self):
        self.exports.getBuildNotificationBlock.return_value = {'user_id': self.user_id}
        self.exports.getLoggedInUser.return_value = {'id': 1}
        self.exports.hasPerm.return_value = False

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.deleteNotificationBlock(self.n_id)
        self.assertEqual(f'user 1 cannot delete notification blocks for user {self.user_id}',
                         str(cm.exception))
        self.assertEqual(len(self.deletes), 0)

        self.exports.getBuildNotificationBlock.assert_called_once_with(self.n_id, strict=True)
