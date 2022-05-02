import mock
import unittest
import koji
import kojihub


class TestGetBuildNotifications(unittest.TestCase):
    def setUp(self):
        self.exports = kojihub.RootExports()
        self.get_user = mock.patch('kojihub.get_user').start()
        self.get_build_notifications = mock.patch('kojihub.get_build_notifications').start()

    def test_loggedin_user(self):
        self.get_user.return_value = {'id': 1}
        kojihub.RootExports().getBuildNotifications(None)
        self.get_user.assert_called_once_with(None, strict=True)
        self.get_build_notifications.assert_called_once_with(1)

    def test_user_not_found(self):
        self.get_user.side_effect = koji.GenericError('error msg')
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.RootExports().getBuildNotifications(1)
        self.get_user.assert_called_once_with(1, strict=True)
        self.get_build_notifications.assert_not_called()
        self.assertEqual(cm.exception.args[0], 'error msg')
