import mock
import unittest
import koji
import kojihub
import shutil
import tempfile
import copy

IP = kojihub.InsertProcessor


class TestImportRPM(unittest.TestCase):

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.tempdir = tempfile.mkdtemp()
        self.filename = self.tempdir + "/name-version-release.arch.rpm"
        # Touch a file
        with open(self.filename, 'w'):
            pass
        self.src_filename = self.tempdir + "/name-version-release.src.rpm"
        # Touch a file
        with open(self.src_filename, 'w'):
            pass
        self.context = mock.patch('kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.context_db = mock.patch('koji.db.context').start()
        self.cursor = mock.MagicMock()

        self.rpm_header_retval = {
            'filename': 'name-version-release.arch.rpm',
            'sourcepackage': 2,
            1000: 'name',
            1001: 'version',
            1002: 'release',
            1003: 'epoch',
            1006: 'buildtime',
            1022: 'arch',
            1044: 'name-version-release.arch',
            1106: 'sourcepackage',
            261: 'payload hash',
        }
        self.get_build = mock.patch('kojihub.get_build').start()
        self.get_rpm_header = mock.patch('koji.get_rpm_header').start()
        self.new_typed_build = mock.patch('kojihub.new_typed_build').start()
        self.nextval = mock.patch('kojihub.nextval').start()
        self.os_path_exists = mock.patch('os.path.exists').start()
        self.os_path_basename = mock.patch('os.path.basename').start()
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        mock.patch.stopall()

    def test_nonexistant_rpm(self):
        with self.assertRaises(koji.GenericError):
            kojihub.import_rpm("this does not exist")

    def test_import_rpm_failed_build(self):
        self.get_rpm_header.return_value = self.rpm_header_retval
        self.get_build.return_value = {
            'state': koji.BUILD_STATES['FAILED'],
            'name': 'name',
            'version': 'version',
            'release': 'release',
        }
        with self.assertRaises(koji.GenericError):
            kojihub.import_rpm(self.filename)
        self.assertEqual(len(self.inserts), 0)

    def test_import_rpm_completed_build(self):
        self.os_path_basename.return_value = 'name-version-release.arch.rpm'
        self.get_rpm_header.return_value = self.rpm_header_retval
        self.get_build.return_value = {
            'state': koji.BUILD_STATES['COMPLETE'],
            'name': 'name',
            'version': 'version',
            'release': 'release',
            'id': 12345,
        }
        self.nextval.return_value = 9876
        kojihub.import_rpm(self.filename)

        data = {
            'build_id': 12345,
            'name': 'name',
            'arch': 'arch',
            'buildtime': 'buildtime',
            'payloadhash': '7061796c6f61642068617368',
            'epoch': 'epoch',
            'version': 'version',
            'buildroot_id': None,
            'release': 'release',
            'external_repo_id': 0,
            'id': 9876,
            'size': 0,
        }
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'rpminfo')
        self.assertEqual(insert.data, data)
        self.assertEqual(insert.rawdata, {})

    def test_import_rpm_completed_source_build(self):
        self.os_path_basename.return_value = 'name-version-release.src.rpm'
        retval = copy.copy(self.rpm_header_retval)
        retval.update({
            'filename': 'name-version-release.arch.rpm',
            1044: 'name-version-release.src',
            1022: 'src',
            1106: 1,
        })
        self.get_rpm_header.return_value = retval
        self.get_build.return_value = {
            'state': koji.BUILD_STATES['COMPLETE'],
            'name': 'name',
            'version': 'version',
            'release': 'release',
            'id': 12345,
        }
        self.nextval.return_value = 9876
        kojihub.import_rpm(self.src_filename)
        data = {
            'build_id': 12345,
            'name': 'name',
            'arch': 'src',
            'buildtime': 'buildtime',
            'payloadhash': '7061796c6f61642068617368',
            'epoch': 'epoch',
            'version': 'version',
            'buildroot_id': None,
            'release': 'release',
            'external_repo_id': 0,
            'id': 9876,
            'size': 0,
        }
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'rpminfo')
        self.assertEqual(insert.data, data)
        self.assertEqual(insert.rawdata, {})

    def test_non_exist_file(self):
        basename = 'rpm-1-34'
        self.os_path_exists.return_value = False
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.import_rpm(self.filename, basename)
        self.assertEqual(f"No such file: {self.filename}", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)

    def test_non_exist_build(self):
        self.cursor.fetchone.return_value = None
        self.context_db.cnx.cursor.return_value = self.cursor
        retval = copy.copy(self.rpm_header_retval)
        retval.update({
            'filename': 'name-version-release.arch.rpm',
            'sourcepackage': 2
        })
        self.get_rpm_header.return_value = retval
        self.os_path_exists.return_value = True
        self.os_path_basename.return_value = 'name-version-release.arch.rpm'
        kojihub.get_build.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.import_rpm(self.src_filename)
        self.assertEqual("No such build", str(cm.exception))
        self.assertEqual(len(self.inserts), 0)
