import unittest

import mock

import koji
import kojihub

IP = kojihub.InsertProcessor


class TestAddBType(unittest.TestCase):

    @mock.patch('kojihub.verify_name_internal')
    @mock.patch('kojihub.list_btypes')
    @mock.patch('kojihub.InsertProcessor')
    def test_add_btype(self, InsertProcessor, list_btypes, verify_name_internal):
        # Not sure why mock can't patch kojihub.context, so we do this
        session = kojihub.context.session = mock.MagicMock()
        mocks = [InsertProcessor, list_btypes, session]
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        session.assertPerm = mock.MagicMock()
        verify_name_internal.return_value = None

        # expected case
        list_btypes.return_value = None
        insert = InsertProcessor.return_value
        kojihub.add_btype('new_btype')
        InsertProcessor.assert_called_once()
        insert.execute.assert_called_once()

        args, kwargs = InsertProcessor.call_args
        ip = IP(*args, **kwargs)
        self.assertEqual(ip.table, 'btype')
        self.assertEqual(ip.data, {'name': 'new_btype'})
        self.assertEqual(ip.rawdata, {})
        session.assertPerm.assert_called_with('admin')

        for m in mocks:
            m.reset_mock()
        session.assertPerm = mock.MagicMock()

        # already exists
        list_btypes.return_value = True
        with self.assertRaises(koji.GenericError):
            kojihub.add_btype('new_btype')
        InsertProcessor.assert_not_called()
        session.assertPerm.assert_called_with('admin')

        # name is longer as expected
        new_btype = 'new-btype+'
        verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_btype(new_btype)

        # not except regex rules
        verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_btype(new_btype)
