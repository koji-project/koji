import unittest

import mock

import koji
import kojihub


UP = kojihub.UpdateProcessor


class TestEditPermission(unittest.TestCase):

    def setUp(self):
        self.lookup_perm = mock.patch('kojihub.lookup_perm').start()
        self.update_processor = mock.patch('kojihub.UpdateProcessor').start()
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()
        self.perm_name = 'test_perms'
        self.perm_info = {'id': 1, 'name': self.perm_name}
        self.description = 'test-description'

    def test_edit_permission_non_exist_permission(self):
        self.lookup_perm.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.editPermission(self.perm_name, self.description)
        self.update_processor.assert_not_called()
        self.context.session.assertPerm.assert_called_with('admin')

    def test_edit_permission(self):
        self.lookup_perm.return_value = self.perm_info
        update = self.update_processor.return_value
        self.exports.editPermission(self.perm_name, self.description)
        self.update_processor.assert_called_once()
        update.execute.assert_called_once()
        args, kwargs = self.update_processor.call_args
        up = UP(*args, **kwargs)
        self.assertEqual(up.table, 'permissions')
        self.assertEqual(up.rawdata, {})
        self.context.session.assertPerm.assert_called_with('admin')

    def test_edit_permission_wrong_type_permission(self):
        description = ['test-description']
        with self.assertRaises(koji.GenericError) as ex:
            self.exports.editPermission(self.perm_name, description=description)
        self.assertEqual(f"Invalid type for value '{description}': {type(description)}, "
                         f"expected type <class 'str'>", str(ex.exception))
        self.update_processor.assert_not_called()
        self.context.session.assertPerm.assert_called_with('admin')
