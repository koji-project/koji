import copy
import mock
import unittest
import shutil
import tempfile

import koji
import kojihub


class TestImportBuild(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.filename = self.tempdir + "/name-version-release.arch.rpm"
        # Touch a file
        with open(self.filename, 'w'):
            pass
        self.src_filename = self.tempdir + "/name-version-release.src.rpm"
        # Touch a file
        with open(self.src_filename, 'w'):
            pass

        self.check_volume_policy = mock.patch('kojihub.check_volume_policy').start()
        self.new_typed_build = mock.patch('kojihub.new_typed_build').start()
        self._dml = mock.patch('koji.db._dml').start()
        self.nextval = mock.patch('kojihub.nextval').start()
        self.get_build = mock.patch('kojihub.get_build').start()
        self.add_rpm_sig = mock.patch('kojihub.add_rpm_sig').start()
        self.rip_rpm_sighdr = mock.patch('koji.rip_rpm_sighdr').start()
        self.import_rpm_file = mock.patch('kojihub.import_rpm_file').start()
        self.import_rpm = mock.patch('kojihub.import_rpm').start()
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor').start()
        self.context = mock.patch('kojihub.context').start()
        self.context_db = mock.patch('koji.db.context').start()
        self.new_package = mock.patch('kojihub.new_package').start()
        self.get_rpm_header = mock.patch('koji.get_rpm_header').start()
        self.pathinfo_work = mock.patch('koji.pathinfo.work').start()
        self.os_path_exists = mock.patch('os.path.exists').start()

        self.rpm_header_retval = {
            'filename': 'name-version-release.arch.rpm',
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

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        mock.patch.stopall()

    def test_import_build_completed_build(self):

        self.rip_rpm_sighdr.return_value = (0, 0)

        processor = mock.MagicMock()
        processor.executeOne.return_value = None
        self.QueryProcessor.return_value = processor

        self.context.session.user_id = 99

        self.pathinfo_work.return_value = '/'

        self.check_volume_policy.return_value = {'id': 0, 'name': 'DEFAULT'}

        retval = copy.copy(self.rpm_header_retval)
        retval.update({
            'filename': 'name-version-release.arch.rpm',
            1044: 'name-version-release.src',
            1022: 'src',
            1106: 1,
        })
        self.get_rpm_header.return_value = retval
        binfo = {
            'state': koji.BUILD_STATES['COMPLETE'],
            'name': 'name',
            'version': 'version',
            'release': 'release',
            'id': 12345,
        }
        # get_build called once to check for existing,
        # if it doesn't exist, called another time after creating
        # then 3rd later to get the build info
        self.get_build.side_effect = [None, binfo, binfo]

        kojihub.import_build(self.src_filename, [self.filename])

        fields = [
            'completion_time',
            'epoch',
            'extra',
            'id',
            'owner',
            'pkg_id',
            'release',
            'source',
            'start_time',
            'state',
            'task_id',
            'version',
            'volume_id',
        ]
        statement = 'INSERT INTO build (%s) VALUES (%s)' % (
            ", ".join(fields),
            ", ".join(['%%(%s)s' % field for field in fields])
        )
        values = {
            'task_id': None,
            'extra': None,
            'start_time': 'NOW',
            'epoch': 'epoch',
            'completion_time': 'NOW',
            'state': 1,
            'version': 'version',
            'source': None,
            'volume_id': 0,
            'owner': 99,
            'release': 'release',
            'pkg_id': mock.ANY,
            'id': mock.ANY,
        }
        self._dml.assert_called_once_with(statement, values)

    def test_import_build_non_exist_file(self):
        uploadpath = koji.pathinfo.work()
        self.os_path_exists.return_value = False
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.import_build(self.src_filename, [self.filename])
        self.assertEqual(f"No such file: {uploadpath}/{self.src_filename}", str(cm.exception))

    def test_import_build_wrong_type_brmap(self):
        brmap = 'test-brmap'
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.import_build(self.src_filename, [self.filename], brmap=brmap)
        self.assertEqual(f"Invalid type for value '{brmap}': {type(brmap)}, "
                         f"expected type <class 'dict'>", str(cm.exception))

    def test_import_build_wrong_type_srpm(self):
        srpm = ['test-srpm']
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.import_build(srpm, [self.filename])
        self.assertEqual(f"Invalid type for value '{srpm}': {type(srpm)}, "
                         f"expected type <class 'str'>", str(cm.exception))

    def test_import_build_wrong_type_rpms(self):
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.import_build(self.src_filename, self.filename)
        self.assertEqual(f"Invalid type for value '{self.filename}': {type(self.filename)}, "
                         f"expected type <class 'list'>",
                         str(cm.exception))
