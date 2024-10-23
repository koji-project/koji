import unittest

from unittest import mock

import koji
import kojihub

IP = kojihub.InsertProcessor


class TestAddBType(unittest.TestCase):

    def setUp(self):
        self.verify_name_internal = mock.patch('kojihub.kojihub.verify_name_internal').start()
        self.list_btypes = mock.patch('kojihub.kojihub.list_btypes').start()
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.session = self.context.session
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.session.assertPerm = mock.MagicMock()
        self.verify_name_internal.return_value = None

    def tearDown(self):
        mock.patch.stopall()

    def test_add_btype(self):
        # expected case
        self.list_btypes.return_value = None
        insert = self.InsertProcessor.return_value
        kojihub.add_btype('new_btype')
        self.InsertProcessor.assert_called_once()
        insert.execute.assert_called_once()

        args, kwargs = self.InsertProcessor.call_args
        ip = IP(*args, **kwargs)
        self.assertEqual(ip.table, 'btype')
        self.assertEqual(ip.data, {'name': 'new_btype'})
        self.assertEqual(ip.rawdata, {})
        self.session.assertPerm.assert_called_with('admin')

    def test_btype_exists(self):
        # already exists
        self.list_btypes.return_value = True
        with self.assertRaises(koji.GenericError):
            kojihub.add_btype('new_btype')
        self.InsertProcessor.assert_not_called()
        self.session.assertPerm.assert_called_with('admin')

    def test_btype_badname(self):
        # name is longer as expected
        new_btype = 'new-btype+'
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_btype(new_btype)


# the end
