from unittest import mock
import unittest
import koji
import kojihub


class TestImportArchive(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.exports = kojihub.RootExports()
        self.context.session.assertPerm = mock.MagicMock()
        self.filepath = 'path/to/file'
        self.buildinfo = 'build-1-1.4'
        self.type_archive = 'maven'
        self.typeinfo = {'group_id': 1, 'artifact_id': 2, 'version': 1}

    def tearDown(self):
        mock.patch.stopall()

    def test_maven_not_enabled(self):
        self.context.opts.get.return_value = False
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.importArchive(self.filepath, self.buildinfo, self.type_archive,
                                       self.typeinfo)
        self.assertEqual("Maven support not enabled", str(cm.exception))

    def test_win_not_enabled(self):
        type_archive = 'win'
        self.context.opts.get.return_value = False
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.importArchive(self.filepath, self.buildinfo, type_archive, self.typeinfo)
        self.assertEqual("Windows support not enabled", str(cm.exception))

    def test_unsupported_type(self):
        type_archive = 'test-type'
        self.context.opts.get.return_value = False
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.importArchive(self.filepath, self.buildinfo, type_archive, self.typeinfo)
        self.assertEqual(f"unsupported archive type: {type_archive}", str(cm.exception))
