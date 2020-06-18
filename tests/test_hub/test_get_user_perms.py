import mock
import unittest
import koji
import kojihub


class TestGetUserPerms(unittest.TestCase):
    def setUp(self):
        self.get_user = mock.patch('kojihub.get_user').start()
        self.get_user_perms = mock.patch('koji.auth.get_user_perms').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_no_user(self):
        self.get_user.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.RootExports().getUserPerms(123)
        self.get_user_perms.assert_not_called()

    def test_normal(self):
        self.get_user.return_value = {'id': 123, 'name': 'testuser'}
        kojihub.RootExports().getUserPerms(123)
        self.get_user_perms.assert_called_once_with(123)
