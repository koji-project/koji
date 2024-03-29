import unittest

import mock

import koji
import kojihub


IP = kojihub.InsertProcessor
UP = kojihub.UpdateProcessor


class TestGrantPermission(unittest.TestCase):

    def setUp(self):
        self.verify_name_internal = mock.patch('kojihub.kojihub.verify_name_internal').start()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.lookup_perm = mock.patch('kojihub.kojihub.lookup_perm').start()
        self.insert_processor = mock.patch('kojihub.kojihub.InsertProcessor').start()
        self.update_processor = mock.patch('kojihub.kojihub.UpdateProcessor').start()
        self.get_user_perms = mock.patch('kojihub.kojihub.get_user_perms').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context_db = mock.patch('kojihub.db.context').start()
        self.exports = kojihub.RootExports()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()
        self.user_name = 'test_user'
        self.perms_name = 'test_perms'
        self.userinfo = {'id': 1, 'krb_principals': [], 'name': self.user_name,
                         'status': 0, 'usertype': 0}
        self.perm_info = {'id': 1, 'name': self.perms_name}

    def tearDown(self):
        mock.patch.stopall()

    def test_grant_permission_wrong_format(self):
        perms_name = 'test-perms+'

        # name is longer as expected
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.grantPermission(self.user_name, perms_name, create=True)
        self.insert_processor.assert_not_called()

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.grantPermission(self.user_name, perms_name, create=True)
        self.insert_processor.assert_not_called()
        self.context.session.assertPerm.assert_called_with('admin')

    def test_grant_permission_description_without_create(self):
        self.verify_name_internal.return_value = None
        with self.assertRaises(koji.GenericError) as ex:
            self.exports.grantPermission(self.user_name, self.perms_name,
                                         description='test-description')
        self.assertEqual("Description should be specified only with create.", str(ex.exception))
        self.insert_processor.assert_not_called()
        self.context.session.assertPerm.assert_called_with('admin')

    def test_grant_permission_non_exist_user(self):
        self.verify_name_internal.return_value = None
        self.get_user.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.grantPermission(self.user_name, self.perms_name)
        self.insert_processor.assert_not_called()
        self.context.session.assertPerm.assert_called_with('admin')

    def test_grant_permission_non_exist_permission_without_new(self):
        self.verify_name_internal.return_value = None
        self.get_user.return_value = self.userinfo
        self.lookup_perm.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.grantPermission(self.user_name, self.perms_name)
        self.insert_processor.assert_not_called()
        self.context.session.assertPerm.assert_called_with('admin')

    def test_grant_permission(self):
        self.verify_name_internal.return_value = None
        self.get_user.return_value = self.userinfo
        self.lookup_perm.return_value = self.perm_info
        self.get_user_perms.return_value = []
        insert = self.insert_processor.return_value
        self.exports.grantPermission(self.user_name, self.perms_name, create=True)
        self.insert_processor.assert_called_once()
        insert.execute.assert_called_once()
        args, kwargs = self.insert_processor.call_args
        ip = IP(*args, **kwargs)
        self.assertEqual(ip.table, 'user_perms')
        self.assertEqual(ip.rawdata, {})
        self.context.session.assertPerm.assert_called_with('admin')

    def test_grant_permission_exist_perms(self):
        self.verify_name_internal.return_value = None
        self.get_user.return_value = self.userinfo
        self.lookup_perm.return_value = self.perm_info
        self.get_user_perms.return_value = [self.perms_name]
        with self.assertRaises(koji.GenericError) as ex:
            self.exports.grantPermission(self.user_name, self.perms_name)
        self.assertEqual(f'user {self.user_name} already has permission: {self.perm_info["name"]}',
                         str(ex.exception))
        self.insert_processor.assert_not_called()
        self.context.session.assertPerm.assert_called_with('admin')

    def test_grant_permission_with_description(self):
        self.verify_name_internal.return_value = None
        self.get_user.return_value = self.userinfo
        self.lookup_perm.return_value = self.perm_info
        self.get_user_perms.return_value = []
        insert = self.insert_processor.return_value
        update = self.update_processor.return_value
        self.exports.grantPermission(self.user_name, self.perms_name, create=True,
                                     description='test-description')
        self.update_processor.assert_called_once()
        update.execute.assert_called_once()
        args, kwargs = self.update_processor.call_args
        up = UP(*args, **kwargs)
        self.assertEqual(up.table, 'permissions')
        self.assertEqual(up.rawdata, {})
        self.insert_processor.assert_called_once()
        insert.execute.assert_called_once()
        args, kwargs = self.insert_processor.call_args
        ip = IP(*args, **kwargs)
        self.assertEqual(ip.table, 'user_perms')
        self.assertEqual(ip.rawdata, {})
        self.context.session.assertPerm.assert_called_with('admin')

    def test_grant_permission_description_wrong_type(self):
        description = ['test-description']
        with self.assertRaises(koji.ParameterError) as ex:
            self.exports.grantPermission(self.user_name, self.perms_name,
                                         description=description, create=True)
        self.assertEqual(f"Invalid type for value '{description}': {type(description)}, "
                         f"expected type <class 'str'>", str(ex.exception))
        self.insert_processor.assert_not_called()
        self.context.session.assertPerm.assert_called_with('admin')
