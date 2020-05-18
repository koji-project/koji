import unittest
import mock

import koji
import kojihub

IP = kojihub.InsertProcessor


class TestAddArchiveType(unittest.TestCase):

    @mock.patch('kojihub._multiRow')
    @mock.patch('kojihub.get_archive_type')
    @mock.patch('kojihub.InsertProcessor')
    def test_add_archive_type(self, InsertProcessor, get_archive_type,
                              _multiRow):
        # Not sure why mock can't patch kojihub.context, so we do this
        session = kojihub.context.session = mock.MagicMock()
        mocks = [InsertProcessor, get_archive_type, session]
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        session.assertPerm = mock.MagicMock()

        # expected case
        get_archive_type.return_value = None
        insert = InsertProcessor.return_value
        kojihub.add_archive_type('deb', 'Debian package', 'deb')
        InsertProcessor.assert_called_once()
        insert.execute.assert_called_once()

        args, kwargs = InsertProcessor.call_args
        ip = IP(*args, **kwargs)
        self.assertEquals(ip.table, 'archivetypes')
        self.assertEquals(ip.data, {'name': 'deb',
                                    'description': 'Debian package',
                                    'extensions': 'deb'})
        self.assertEquals(ip.rawdata, {})
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
