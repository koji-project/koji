import os.path
import shutil
import tempfile
from unittest import mock
import unittest

import koji
import kojihub
from .utils import DBQueryTestCase


class TestGetRPM(DBQueryTestCase):

    def setUp(self):
        super(TestGetRPM, self).setUp()
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.get_external_repo_id = mock.patch('kojihub.kojihub.get_external_repo_id').start()
        self.find_build_id = mock.patch('kojihub.kojihub.find_build_id').start()
    
    def tearDown(self):
        mock.patch.stopall()

    def test_wrong_type_rpminfo(self):
        rpminfo = ['test-user']
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_rpm(rpminfo)
        self.assertEqual(f"Invalid type for rpminfo: {type(rpminfo)}", str(cm.exception))

    def test_rpm_info_int(self):
        rpminfo = 123
        self.qp_execute_return_value = [{'rpminfo.id': 123}]
        result = kojihub.get_rpm(rpminfo)
        self.assertEqual(result, {'rpminfo.id': 123})

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpminfo'])
        columns = ['rpminfo.id', 'build_id', 'buildroot_id', 'rpminfo.name', 'version', 'release',
                   'epoch', 'arch', 'draft', 'external_repo_id', 'external_repo.name',
                   'payloadhash', 'size', 'buildtime', 'metadata_only', 'extra']
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(query.clauses, ["rpminfo.id=%(id)s"])
        self.assertEqual(query.joins,
                         ['external_repo ON rpminfo.external_repo_id = external_repo.id'])
        self.assertEqual(query.values, {'id': rpminfo})

    def test_rpm_info_empty_query_result_without_strict(self):
        rpminfo = 123
        self.qp_execute_one_return_value = {}
        result = kojihub.get_rpm(rpminfo)
        self.assertEqual(result, None)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpminfo'])
        columns = ['rpminfo.id', 'build_id', 'buildroot_id', 'rpminfo.name', 'version', 'release',
                   'epoch', 'arch', 'draft', 'external_repo_id', 'external_repo.name',
                   'payloadhash', 'size', 'buildtime', 'metadata_only', 'extra']
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(query.clauses, ["rpminfo.id=%(id)s"])
        self.assertEqual(query.joins,
                         ['external_repo ON rpminfo.external_repo_id = external_repo.id'])
        self.assertEqual(query.values, {'id': rpminfo})

    def test_rpm_info_empty_query_result_with_strict(self):
        rpminfo = 123
        self.qp_execute_one_return_value = {}
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.get_rpm(rpminfo, strict=True)
        self.assertEqual("No such rpm: {'id': 123}", str(ex.exception))

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpminfo'])
        columns = ['rpminfo.id', 'build_id', 'buildroot_id', 'rpminfo.name', 'version', 'release',
                   'epoch', 'arch', 'draft', 'external_repo_id', 'external_repo.name',
                   'payloadhash', 'size', 'buildtime', 'metadata_only', 'extra']
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(query.clauses, ["rpminfo.id=%(id)s"])
        self.assertEqual(query.joins,
                         ['external_repo ON rpminfo.external_repo_id = external_repo.id'])
        self.assertEqual(query.values, {'id': rpminfo})

    def test_rpm_info_str(self):
        rpminfo = 'testrpm-1.23-4.x86_64.rpm'
        kojihub.get_rpm(rpminfo, multi=True)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpminfo'])
        columns = ['rpminfo.id', 'build_id', 'buildroot_id', 'rpminfo.name', 'version', 'release',
                   'epoch', 'arch', 'draft', 'external_repo_id', 'external_repo.name',
                   'payloadhash', 'size', 'buildtime', 'metadata_only', 'extra']
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(query.clauses, ["rpminfo.name=%(name)s AND version=%(version)s "
                                         "AND release=%(release)s AND arch=%(arch)s"])
        self.assertEqual(query.joins,
                         ['external_repo ON rpminfo.external_repo_id = external_repo.id'])
        self.assertEqual(query.values, {'arch': 'x86_64', 'epoch': '', 'name': 'testrpm',
                                        'release': '4', 'src': False, 'version': '1.23'})

    def test_rpm_info_dict_location(self):
        rpminfo = {'id': 123, 'name': 'testrpm-1.23-4.x86_64.rpm', 'location': 'test-location'}
        self.get_external_repo_id.return_value = 125
        rpminfo_data = rpminfo.copy()
        rpminfo_data['external_repo_id'] = 125

        kojihub.get_rpm(rpminfo, multi=True)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['rpminfo'])
        columns = ['rpminfo.id', 'build_id', 'buildroot_id', 'rpminfo.name', 'version', 'release',
                   'epoch', 'arch', 'draft', 'external_repo_id', 'external_repo.name',
                   'payloadhash', 'size', 'buildtime', 'metadata_only', 'extra']
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(query.clauses,
                         ["external_repo_id = %(external_repo_id)s", "rpminfo.id=%(id)s"])
        self.assertEqual(query.joins,
                         ['external_repo ON rpminfo.external_repo_id = external_repo.id'])
        self.assertEqual(query.values, rpminfo_data)

    @mock.patch('kojihub.kojihub._get_rpms')
    def test_rpm_info_preferred(self, _get_rpms):
        rpminfo = 'testrpm-1.23-4.x86_64.rpm'
        rpm_ext = {'id': 1, 'external_repo_id': 2, 'draft': False}
        rpm_ext2 = {'id': 2, 'external_repo_id': 2, 'draft': False}
        rpm_draft = {'id': 3, 'external_repo_id': 0, 'draft': True}
        rpm_draft2 = {'id': 4, 'external_repo_id': 0, 'draft': True}
        rpm_nondraft = {'id': 5, 'external_repo_id': 0, 'draft': False}

        # this test checks that the expected preferences are followed for multiple matches

        _get_rpms.return_value = [rpm_ext, rpm_ext2, rpm_draft, rpm_draft2, rpm_nondraft]
        ret = kojihub.get_rpm(rpminfo, multi=False)
        self.assertEqual(ret, rpm_nondraft)

        _get_rpms.return_value = [rpm_ext, rpm_ext2, rpm_draft, rpm_draft2]
        ret = kojihub.get_rpm(rpminfo, multi=False)
        self.assertEqual(ret, rpm_draft2)

        _get_rpms.return_value = [rpm_ext, rpm_ext2, rpm_draft]
        ret = kojihub.get_rpm(rpminfo, multi=False)
        self.assertEqual(ret, rpm_draft)

        _get_rpms.return_value = [rpm_ext, rpm_ext2]
        ret = kojihub.get_rpm(rpminfo, multi=False)
        self.assertEqual(ret, rpm_ext2)

        _get_rpms.return_value = [rpm_ext]
        ret = kojihub.get_rpm(rpminfo, multi=False)
        self.assertEqual(ret, rpm_ext)

        # multiple nondraft matches should error
        rpm_bad = {'id': 6, 'external_repo_id': 0, 'draft': False}
        _get_rpms.return_value = [rpm_nondraft, rpm_bad]
        with self.assertRaises(koji.GenericError):
            ret = kojihub.get_rpm(rpminfo, multi=False)

        self.assertEqual(len(self.queries), 0)  # _get_rpm is mocked


class TestGetRPMHeaders(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.exports.getLoggedInUser = mock.MagicMock()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.cursor = mock.MagicMock()
        self.get_rpm = mock.patch('kojihub.kojihub.get_rpm').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.get_header_fields = mock.patch('koji.get_header_fields').start()
        self.tempdir = tempfile.mkdtemp()
        self.pathinfo = koji.PathInfo(self.tempdir)
        mock.patch('koji.pathinfo', new=self.pathinfo).start()

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.tempdir)

    def test_taskid_invalid_path(self):
        self.cursor.fetchone.return_value = None
        self.context.cnx.cursor.return_value = self.cursor
        filepath = '../test/path'
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getRPMHeaders(taskID=99, filepath=filepath)
        self.assertEqual(f"Invalid filepath: {filepath}", str(cm.exception))
        self.get_rpm.assert_not_called()
        self.get_build.assert_not_called()
        self.get_header_fields.assert_not_called()

    def test_taskid_without_filepath(self):
        self.cursor.fetchone.return_value = None
        self.context.cnx.cursor.return_value = self.cursor
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getRPMHeaders(taskID=99)
        self.assertEqual("filepath must be specified with taskID", str(cm.exception))
        self.get_rpm.assert_not_called()
        self.get_build.assert_not_called()
        self.get_header_fields.assert_not_called()

    def test_insufficient_args(self):
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getRPMHeaders(strict=False)
        self.assertEqual("either rpmID or taskID and filepath must be specified",
                         str(cm.exception))
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getRPMHeaders(filepath='something')
        self.assertEqual("either rpmID or taskID and filepath must be specified",
                         str(cm.exception))
        # we already test taskid without filepath above

    def test_unknown_rpm(self):
        self.get_rpm.return_value = None
        result = self.exports.getRPMHeaders(rpmID='FOO-1-1.noarch', strict=False)
        self.assertEqual(result, {})
        self.get_rpm.assert_called_with('FOO-1-1.noarch', strict=False)

        # again with strict mode
        self.get_rpm.side_effect = koji.GenericError('NO SUCH RPM')
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getRPMHeaders(rpmID='FOO-1-1.noarch', strict=True)
        self.assertEqual("NO SUCH RPM", str(cm.exception))
        self.get_rpm.assert_called_with('FOO-1-1.noarch', strict=True)
        self.get_build.assert_not_called()
        self.get_header_fields.assert_not_called()

    def test_external_rpm(self):
        rpm_info = {'external_repo_id': 1, 'id': 'RPMID'}
        self.get_rpm.return_value = rpm_info
        result = self.exports.getRPMHeaders(rpmID='FOO-1-1.noarch', strict=False)
        self.assertEqual(result, {})

        # again with strict mode
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getRPMHeaders(rpmID='FOO-1-1.noarch', strict=True)
        self.assertEqual(f"External rpm: {rpm_info['id']}", str(cm.exception))
        self.get_build.assert_not_called()
        self.get_header_fields.assert_not_called()

    def test_deleted_build(self):
        self.get_rpm.return_value = {'build_id': 'BUILDID', 'external_repo_id': 0}
        build_info = {'nvr': 'NVR', 'state': koji.BUILD_STATES['DELETED']}
        self.get_build.return_value = build_info
        result = self.exports.getRPMHeaders(rpmID='FOO-1-1.noarch', strict=False)
        self.assertEqual(result, {})
        self.get_build.assert_called_with('BUILDID', strict=True)

        # again with strict mode
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getRPMHeaders(rpmID='FOO-1-1.noarch', strict=True)
        self.assertEqual(f"Build {build_info['nvr']} is deleted", str(cm.exception))
        self.get_build.assert_called_with('BUILDID', strict=True)
        self.get_header_fields.assert_not_called()

    def test_missing_rpm(self):
        self.get_rpm.return_value = {
            'build_id': 'BUILDID',
            'external_repo_id': 0,
            'name': 'pkg',
            'version': '1',
            'release': '2',
            'arch': 'noarch'}
        self.get_build.return_value = {
            'name': 'pkg',
            'version': '1',
            'release': '2',
            'nvr': 'pkg-1-2',
            'state': koji.BUILD_STATES['COMPLETE']}
        rpmpath = '%s/packages/pkg/1/2/noarch/pkg-1-2.noarch.rpm' % self.tempdir

        # rpm does not exist
        result = self.exports.getRPMHeaders(rpmID='pkg-1-2.noarch', strict=False)
        self.assertEqual(result, {})
        self.get_build.assert_called_with('BUILDID', strict=True)

        # again with strict mode
        with self.assertRaises(koji.GenericError) as e:
            self.exports.getRPMHeaders(rpmID='FOO-1-1.noarch', strict=True)
        self.assertEqual(f"Missing rpm file: {rpmpath}", str(e.exception))
        self.get_build.assert_called_with('BUILDID', strict=True)
        self.get_header_fields.assert_not_called()

    def test_rpm_exists(self):
        self.get_rpm.return_value = {
            'build_id': 'BUILDID',
            'external_repo_id': 0,
            'name': 'pkg',
            'version': '1',
            'release': '2',
            'arch': 'noarch'}
        self.get_build.return_value = {
            'name': 'pkg',
            'version': '1',
            'release': '2',
            'nvr': 'pkg-1-2',
            'state': koji.BUILD_STATES['COMPLETE']}
        rpmpath = '%s/packages/pkg/1/2/noarch/pkg-1-2.noarch.rpm' % self.tempdir
        koji.ensuredir(os.path.dirname(rpmpath))
        with open(rpmpath, 'w') as fo:
            fo.write('hello world')
        fakeheaders = {'HEADER': 'SOMETHING'}
        self.get_header_fields.return_value = fakeheaders

        result = self.exports.getRPMHeaders(rpmID='pkg-1-2.noarch', strict=True)
        self.assertEqual(result, fakeheaders)
        self.get_build.assert_called_with('BUILDID', strict=True)
        self.get_header_fields.assert_called_with(rpmpath, None)

    def test_task_rpm_exists(self):
        taskid = 137
        filepath = 'pkg-1-2.noarch.rpm'
        rpmpath = '%s/work/tasks/137/137/pkg-1-2.noarch.rpm' % self.tempdir
        koji.ensuredir(os.path.dirname(rpmpath))
        with open(rpmpath, 'w') as fo:
            fo.write('hello world')
        fakeheaders = {'HEADER': 'SOMETHING'}
        self.get_header_fields.return_value = fakeheaders

        result = self.exports.getRPMHeaders(taskID=taskid, filepath=filepath, strict=False)
        self.assertEqual(result, fakeheaders)
        self.get_rpm.assert_not_called()
        self.get_build.assert_not_called()
        self.get_header_fields.assert_called_with(rpmpath, None)

    def test_task_rpm_missing(self):
        taskid = 137
        filepath = 'pkg-1-2.noarch.rpm'
        rpmpath = '%s/work/tasks/137/137/pkg-1-2.noarch.rpm' % self.tempdir

        result = self.exports.getRPMHeaders(taskID=taskid, filepath=filepath, strict=False)
        self.assertEqual(result, {})

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getRPMHeaders(taskID=taskid, filepath=filepath, strict=True)
        self.assertEqual(f"Missing rpm file: {rpmpath}", str(cm.exception))
        self.get_rpm.assert_not_called()
        self.get_build.assert_not_called()
        self.get_header_fields.assert_not_called()
