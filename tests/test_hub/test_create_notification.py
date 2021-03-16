import unittest
import mock

import koji
import kojihub


class TestCreateNotification(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.exports.getLoggedInUser = mock.MagicMock()
        self.context = mock.patch('kojihub.context').start()
        self.cursor = mock.MagicMock()

    def test_non_exist_user(self):
        user_id = 999
        package_id = 555
        tag_id = 111
        success_only = False
        logged_user = {'authtype': 2,
                       'id': 1,
                       'krb_principal': None,
                       'krb_principals': [],
                       'name': 'kojiadmin',
                       'status': 0,
                       'usertype': 0}
        self.cursor.fetchone.return_value = None
        self.context.cnx.cursor.return_value = self.cursor
        self.exports.getLoggedInUser.return_value = logged_user
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createNotification(user_id, package_id, tag_id, success_only)
        self.assertEqual('No such user ID: %s' % user_id, str(cm.exception))


class TestCreateNotificationBlock(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.exports.getLoggedInUser = mock.MagicMock()
        self.context = mock.patch('kojihub.context').start()
        self.cursor = mock.MagicMock()

    def test_non_exist_user(self):
        user_id = 999
        package_id = 555
        tag_id = 111
        logged_user = {'authtype': 2,
                       'id': 1,
                       'krb_principal': None,
                       'krb_principals': [],
                       'name': 'kojiadmin',
                       'status': 0,
                       'usertype': 0}
        self.cursor.fetchone.return_value = None
        self.context.cnx.cursor.return_value = self.cursor
        self.exports.getLoggedInUser.return_value = logged_user
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.createNotificationBlock(user_id, package_id, tag_id)
        self.assertEqual('No such user ID: %s' % user_id, str(cm.exception))
