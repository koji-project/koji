import unittest

import mock

import koji
import kojihub

IP = kojihub.InsertProcessor


class TestAddArchiveType(unittest.TestCase):

    @mock.patch('kojihub.verify_name_internal')
    @mock.patch('kojihub._multiRow')
    @mock.patch('kojihub.get_archive_type')
    @mock.patch('kojihub.InsertProcessor')
    def test_add_archive_type(self, InsertProcessor, get_archive_type, _multiRow,
                              verify_name_internal):
        # Not sure why mock can't patch kojihub.context, so we do this
        session = kojihub.context.session = mock.MagicMock()
        mocks = [InsertProcessor, get_archive_type, session]
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        session.assertPerm = mock.MagicMock()
        verify_name_internal.return_value = None

        # expected case
        get_archive_type.return_value = None
        insert = InsertProcessor.return_value
        kojihub.add_archive_type('deb', 'Debian package', 'deb')
        InsertProcessor.assert_called_once()
        insert.execute.assert_called_once()

        args, kwargs = InsertProcessor.call_args
        ip = IP(*args, **kwargs)
        self.assertEqual(ip.table, 'archivetypes')
        self.assertEqual(ip.data, {'name': 'deb',
                                   'description': 'Debian package',
                                   'extensions': 'deb'})
        self.assertEqual(ip.rawdata, {})
        session.assertPerm.assert_called_with('admin')

        for m in mocks:
            m.reset_mock()
        session.assertPerm = mock.MagicMock()

        # already exists
        get_archive_type.return_value = True
        with self.assertRaises(koji.GenericError):
            kojihub.add_archive_type('deb', 'Debian package', 'deb')
        InsertProcessor.assert_not_called()
        session.assertPerm.assert_called_with('admin')

        # name is longer as expected
        new_archive_type = 'new-archive-type+'
        verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_archive_type(new_archive_type, 'Debian package', 'deb')

        # not except regex rules
        verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_archive_type(new_archive_type, 'Debian package', 'deb')
