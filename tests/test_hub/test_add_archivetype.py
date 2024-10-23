from unittest import mock

import koji
import kojihub
import kojihub.kojihub
from .utils import DBQueryTestCase

IP = kojihub.InsertProcessor


class TestAddArchiveType(DBQueryTestCase):
    def setUp(self):
        super(TestAddArchiveType, self).setUp()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.exports = kojihub.RootExports()
        self.channel_name = 'test-channel'
        self.description = 'test-description'
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.insert_execute = mock.MagicMock()
        self.verify_name_internal = mock.patch('kojihub.kojihub.verify_name_internal').start()
        self.get_archive_type = mock.patch('kojihub.kojihub.get_archive_type').start()

    def tearDown(self):
        mock.patch.stopall()

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = self.insert_execute
        self.inserts.append(insert)
        return insert

    def test_add_archive_type_valid_empty_compression_type(self):
        self.qp_execute_side_effect = [[]]
        self.verify_name_internal.return_value = None
        self.get_archive_type.return_value = None
        ext = 'deb'
        rv = kojihub.add_archive_type('deb', 'Debian package', ext)

        self.assertEqual(len(self.queries), 1)
        self.assertLastQueryEqual(tables=['archivetypes'],
                                  columns=['id'],
                                  clauses=[f"extensions ~* E'(\\s|^){ext}(\\s|$)'"],
                                  values={})
        self.assertEqual(rv, None)
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'archivetypes')
        self.assertEqual(insert.data, {'name': 'deb',
                                       'description': 'Debian package',
                                       'extensions': 'deb',
                                       'compression_type': None})
        self.assertEqual(insert.rawdata, {})
        self.context.session.assertPerm.assert_called_with('admin')
        self.get_archive_type.assert_called_once_with(type_name='deb')

    def test_add_archive_type_valid_with_compression_type(self):
        self.qp_execute_side_effect = [[]]
        self.verify_name_internal.return_value = None
        self.get_archive_type.return_value = None
        ext = '.jar'
        kojihub.add_archive_type('jar', 'Jar package', ext, compression_type='zip')

        self.assertEqual(len(self.queries), 1)
        self.assertLastQueryEqual(tables=['archivetypes'],
                                  columns=['id'],
                                  clauses=[f"extensions ~* E'(\\s|^){ext}(\\s|$)'"],
                                  values={})
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'archivetypes')
        self.assertEqual(insert.data, {'name': 'jar',
                                       'description': 'Jar package',
                                       'extensions': '.jar',
                                       'compression_type': 'zip'})
        self.assertEqual(insert.rawdata, {})
        self.context.session.assertPerm.assert_called_with('admin')
        self.get_archive_type.assert_called_once_with(type_name='jar')

    def test_add_archive_type_already_exists(self):
        self.get_archive_type.return_value = True
        name = 'deb'
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.add_archive_type(name, 'Debian package', '.deb')
        self.assertEqual(f"archivetype {name} already exists", str(ex.exception))
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.queries), 0)
        self.context.session.assertPerm.assert_called_with('admin')
        self.get_archive_type.assert_called_once_with(type_name=name)

    def test_add_archive_type_invalid_value_type(self):
        self.verify_name_internal.return_value = None
        description = ['Debian package']
        with self.assertRaises(koji.ParameterError) as ex:
            kojihub.add_archive_type('deb', description, 'deb')
        self.assertEqual(f"Invalid type for value '{description}': {type(description)}, "
                         f"expected type <class 'str'>", str(ex.exception))
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.queries), 0)
        self.context.session.assertPerm.assert_called_with('admin')
        self.get_archive_type.assert_not_called()

    def test_add_archive_type_invalid_value_extensions(self):
        extensions = ['deb']
        with self.assertRaises(koji.ParameterError) as ex:
            kojihub.add_archive_type('deb', 'Debian package', extensions)
        self.assertEqual(f"Invalid type for value '{extensions}': {type(extensions)}, "
                         f"expected type <class 'str'>", str(ex.exception))
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.queries), 0)
        self.context.session.assertPerm.assert_called_with('admin')
        self.get_archive_type.assert_not_called()

    def test_add_archive_type_extension_exists(self):
        ext = '.jar'
        self.qp_execute_side_effect = [{'id': 123}]
        self.get_archive_type.return_value = None
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.add_archive_type('jar', 'Jar package', ext, compression_type='zip')
        self.assertEqual(f'file extension {ext} already exists', str(ex.exception))

        self.assertEqual(len(self.queries), 1)
        self.assertLastQueryEqual(tables=['archivetypes'],
                                  columns=['id'],
                                  clauses=[f"extensions ~* E'(\\s|^){ext}(\\s|$)'"],
                                  values={})
        self.assertEqual(len(self.inserts), 0)
        self.context.session.assertPerm.assert_called_with('admin')
        self.get_archive_type.assert_called_once_with(type_name='jar')

    def test_add_archive_type_unsupported_compression_type(self):
        ext = '.jar'
        compression_type = 'gzip'
        self.qp_execute_side_effect = [{'id': 123}]
        self.get_archive_type.return_value = None
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.add_archive_type('jar', 'Jar package', ext, compression_type=compression_type)
        self.assertEqual(f"Unsupported compression type {compression_type}", str(ex.exception))

        self.assertEqual(len(self.queries), 0)
        self.assertEqual(len(self.inserts), 0)
        self.context.session.assertPerm.assert_called_with('admin')
        self.get_archive_type.assert_not_called()

    def test_add_archive_type_not_alnum(self):
        ext = '.jar@'
        self.get_archive_type.return_value = None
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.add_archive_type('jar', 'Jar package', ext, compression_type='zip')
        self.assertEqual(f'No such {ext} file extension', str(ex.exception))
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.queries), 0)
        self.context.session.assertPerm.assert_called_with('admin')
        self.get_archive_type.assert_called_once_with(type_name='jar')

    def test_add_archive_type_wrong_name_verify(self):
        # name is longer as expected
        new_archive_type = 'new-archive-type+'
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_archive_type(new_archive_type, 'Debian package', 'deb')
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.queries), 0)
        self.get_archive_type.assert_not_called()

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_archive_type(new_archive_type, 'Debian package', 'deb')
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.queries), 0)
        self.get_archive_type.assert_not_called()
