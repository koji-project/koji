import mock
import unittest
import koji
import kojihub


class TestGetBuildNotifications(unittest.TestCase):
    @mock.patch('kojihub.get_user', return_value={'id': 1})
    @mock.patch('kojihub.get_build_notifications')
    def test_loggedin_user(self, get_build_notifications, get_user):
        kojihub.RootExports().getBuildNotifications(None)
        get_user.assert_called_once_with(None, strict=True)
        get_build_notifications.assert_called_once_with(1)

    @mock.patch('kojihub.get_user', side_effect=koji.GenericError('error msg'))
    @mock.patch('kojihub.get_build_notifications')
    def test_user_not_found(self, get_build_notifications, get_user):
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.RootExports().getBuildNotifications(1)
        get_user.assert_called_once_with(1, strict=True)
        get_build_notifications.assert_not_called()
        self.assertEqual(cm.exception.args[0], 'error msg')
