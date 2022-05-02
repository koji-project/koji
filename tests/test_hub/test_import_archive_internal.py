import unittest
import mock

import koji
import kojihub


class TestImportArchiveInternal(unittest.TestCase):
    def setUp(self):
        self.os_path_exists = mock.patch('os.path.exists').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_import_archive_internal_non_exist_filepath(self):
        self.os_path_exists.return_value = False
        filepath = 'test/file/path/to/archive'
        buildinfo = {'id': 1, 'name': 'test-build'}
        type_archive = 'maven'
        typeInfo = {'group_id': 1, 'artifact_id': 2, 'version': 3}
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.import_archive_internal(filepath, buildinfo, type_archive, typeInfo)
        self.assertEqual(f"No such file: {filepath}", str(cm.exception))
