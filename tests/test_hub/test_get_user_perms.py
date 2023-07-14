import mock
import unittest
import koji
from .utils import DBQueryTestCase
import kojihub


class TestGetUserPerms(unittest.TestCase):
    def setUp(self):
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.get_user_perms = mock.patch('kojihub.kojihub.get_user_perms').start()

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
        self.get_user_perms.assert_called_once_with(123, with_groups=True)


class TestGetUserPermsInheritance(DBQueryTestCase):
    def setUp(self):
        super(TestGetUserPermsInheritance, self).setUp()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.get_user_perms = mock.patch('kojihub.kojihub.get_user_perms').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_no_user(self):
        self.get_user.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.RootExports().getUserPermsInheritance(123)
        self.get_user_perms.assert_not_called()

    def test_normal(self):
        self.get_user.return_value = {'id': 123, 'name': 'testuser'}
        self.get_user_perms.return_value = ['test1', 'test2']
        self.qp_execute_return_value = [
            {'permission': 'test2', 'group': 'group1'},
            {'permission': 'test3', 'group': 'group1'},
            {'permission': 'test3', 'group': 'group2'},
        ]
        result = kojihub.RootExports().getUserPermsInheritance(123)
        self.assertEqual(result, {
            'test1': [None],
            'test2': [None, 'group1'],
            'test3': ['group1', 'group2'],
        })
        self.get_user.assert_called_once_with(123, strict=True)
        self.get_user_perms.assert_called_once_with(123, with_groups=False)
