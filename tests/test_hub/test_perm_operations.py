
import mock

import unittest

import koji
import kojihub


class TestPerm(unittest.TestCase):

    @mock.patch('kojihub.context')
    @mock.patch('kojihub.lookup_perm', return_value=None)
    def test_has_perm(self, lookup_perm, context):
        rv = kojihub.RootExports().hasPerm('perm')
        self.assertEqual(rv, context.session.hasPerm.return_value)
        lookup_perm.assert_not_called()
        context.session.hasPerm.assert_called_once_with('perm')

        context.session.hasPerm.reset_mock()
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.RootExports().hasPerm('perm', strict=True)
        lookup_perm.assert_called_once_with('perm')
        context.session.hasPerm.assert_not_called()
        self.assertEqual(cm.exception.args[0],
                         'No such permission perm defined')
