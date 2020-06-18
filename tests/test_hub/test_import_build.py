import copy
import mock
import shutil
import tempfile
import unittest

import koji
import kojihub


class TestImportRPM(unittest.TestCase):
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

    def test_nonexistant_rpm(self):
        with self.assertRaises(koji.GenericError):
            kojihub.import_rpm("this does not exist")

    @mock.patch('kojihub.get_build')
    @mock.patch('koji.get_rpm_header')
    def test_import_rpm_failed_build(self, get_rpm_header, get_build):
        get_rpm_header.return_value = self.rpm_header_retval
        get_build.return_value = {
            'state': koji.BUILD_STATES['FAILED'],
            'name': 'name',
            'version': 'version',
            'release': 'release',
        }
        with self.assertRaises(koji.GenericError):
            kojihub.import_rpm(self.filename)

    @mock.patch('kojihub.new_typed_build')
    @mock.patch('kojihub._dml')
    @mock.patch('kojihub._singleValue')
    @mock.patch('kojihub.get_build')
    @mock.patch('koji.get_rpm_header')
    def test_import_rpm_completed_build(self, get_rpm_header, get_build,
                                        _singleValue, _dml,
                                        new_typed_build):
        get_rpm_header.return_value = self.rpm_header_retval
        get_build.return_value = {
            'state': koji.BUILD_STATES['COMPLETE'],
            'name': 'name',
            'version': 'version',
            'release': 'release',
            'id': 12345,
        }
        _singleValue.return_value = 9876
        kojihub.import_rpm(self.filename)
        fields = [
            'arch',
            'build_id',
            'buildroot_id',
            'buildtime',
            'epoch',
            'external_repo_id',
            'id',
            'name',
            'payloadhash',
            'release',
            'size',
            'version',
        ]
        statement = 'INSERT INTO rpminfo (%s) VALUES (%s)' % (
            ", ".join(fields),
            ", ".join(['%%(%s)s' % field for field in fields])
        )
        values = {
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
        _dml.assert_called_once_with(statement, values)

    @mock.patch('kojihub.new_typed_build')
    @mock.patch('kojihub._dml')
    @mock.patch('kojihub._singleValue')
    @mock.patch('kojihub.get_build')
    @mock.patch('koji.get_rpm_header')
    def test_import_rpm_completed_source_build(self, get_rpm_header, get_build,
                                               _singleValue, _dml,
                                               new_typed_build):
        retval = copy.copy(self.rpm_header_retval)
        retval.update({
            'filename': 'name-version-release.arch.rpm',
            1044: 'name-version-release.src',
            1022: 'src',
            1106: 1,
        })
        get_rpm_header.return_value = retval
        get_build.return_value = {
            'state': koji.BUILD_STATES['COMPLETE'],
            'name': 'name',
            'version': 'version',
            'release': 'release',
            'id': 12345,
        }
        _singleValue.return_value = 9876
        kojihub.import_rpm(self.src_filename)
        fields = [
            'arch',
            'build_id',
            'buildroot_id',
            'buildtime',
            'epoch',
            'external_repo_id',
            'id',
            'name',
            'payloadhash',
            'release',
            'size',
            'version',
        ]
        statement = 'INSERT INTO rpminfo (%s) VALUES (%s)' % (
            ", ".join(fields),
            ", ".join(['%%(%s)s' % field for field in fields])
        )
        values = {
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
        _dml.assert_called_once_with(statement, values)


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

    @mock.patch('kojihub.check_volume_policy')
    @mock.patch('kojihub.new_typed_build')
    @mock.patch('kojihub._dml')
    @mock.patch('kojihub._singleValue')
    @mock.patch('kojihub.get_build')
    @mock.patch('kojihub.add_rpm_sig')
    @mock.patch('koji.rip_rpm_sighdr')
    @mock.patch('kojihub.import_rpm_file')
    @mock.patch('kojihub.import_rpm')
    @mock.patch('kojihub.QueryProcessor')
    @mock.patch('kojihub.context')
    @mock.patch('kojihub.new_package')
    @mock.patch('koji.get_rpm_header')
    @mock.patch('koji.pathinfo.work')
    def test_import_build_completed_build(self, work, get_rpm_header,
                                          new_package, context, query,
                                          import_rpm, import_rpm_file,
                                          rip_rpm_sighdr, add_rpm_sig,
                                          get_build, _singleValue, _dml,
                                          new_typed_build, check_volume_policy):

        rip_rpm_sighdr.return_value = (0, 0)

        processor = mock.MagicMock()
        processor.executeOne.return_value = None
        query.return_value = processor

        context.session.user_id = 99

        work.return_value = '/'

        check_volume_policy.return_value = {'id':0, 'name': 'DEFAULT'}

        retval = copy.copy(self.rpm_header_retval)
        retval.update({
            'filename': 'name-version-release.arch.rpm',
            1044: 'name-version-release.src',
            1022: 'src',
            1106: 1,
        })
        get_rpm_header.return_value = retval
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
        get_build.side_effect = [None, binfo, binfo]

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
        _dml.assert_called_once_with(statement, values)
