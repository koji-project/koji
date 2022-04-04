import unittest

import mock

import koji
import kojihub

IP = kojihub.InsertProcessor


class TestAddArchiveType(unittest.TestCase):

    def setUp(self):

        self.context = mock.patch('kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.exports = kojihub.RootExports()
        self.channel_name = 'test-channel'
        self.description = 'test-description'
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.insert_execute = mock.MagicMock()
        self.verify_name_internal = mock.patch('kojihub.verify_name_internal').start()
        self.get_archive_type = mock.patch('kojihub.get_archive_type').start()
        self._multiRow = mock.patch('kojihub._multiRow').start()

    def tearDown(self):
        mock.patch.stopall()

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = self.insert_execute
        self.inserts.append(insert)
        return insert

    def test_add_archive_type_valid(self):
        self.verify_name_internal.return_value = None
        self.get_archive_type.return_value = None
        kojihub.add_archive_type('deb', 'Debian package', 'deb')

        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'archivetypes')
        self.assertEqual(insert.data, {'name': 'deb',
                                       'description': 'Debian package',
                                       'extensions': 'deb'})
        self.assertEqual(insert.rawdata, {})
        self.context.session.assertPerm.assert_called_with('admin')

    def test_add_archive_type_already_exists(self):
        self.get_archive_type.return_value = True
        with self.assertRaises(koji.GenericError):
            kojihub.add_archive_type('deb', 'Debian package', 'deb')
        self.assertEqual(len(self.inserts), 0)
        self.context.session.assertPerm.assert_called_with('admin')

    def test_add_archive_type_invalid_value_type(self):
        self.verify_name_internal.return_value = None
        description = ['Debian package']
        with self.assertRaises(koji.ParameterError) as ex:
            kojihub.add_archive_type('deb', description, 'deb')
        self.assertEqual(f"Invalid type for value '{description}': {type(description)}",
                         str(ex.exception))

    def test_add_archive_type_invalid_value_extensions(self):
        extensions = ['deb']
        with self.assertRaises(koji.ParameterError) as ex:
            kojihub.add_archive_type('deb', 'Debian package', extensions)
        self.assertEqual(f"Invalid type for value '{extensions}': {type(extensions)}",
                         str(ex.exception))

    def test_add_archive_type_wrong_name_verify(self):
        # name is longer as expected
        new_archive_type = 'new-archive-type+'
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_archive_type(new_archive_type, 'Debian package', 'deb')

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_archive_type(new_archive_type, 'Debian package', 'deb')
