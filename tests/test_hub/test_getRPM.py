import os.path
import shutil
import tempfile
import unittest
import mock

import koji
import kojihub


class TestGetRPM(unittest.TestCase):

    def test_wrong_type_rpminfo(self):
        rpminfo = ['test-user']
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_rpm(rpminfo)
        self.assertEqual(f"Invalid type for rpminfo: {type(rpminfo)}", str(cm.exception))


class TestGetRPMHeaders(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.exports.getLoggedInUser = mock.MagicMock()
        self.context = mock.patch('kojihub.context').start()
        self.cursor = mock.MagicMock()
        self.get_rpm = mock.patch('kojihub.get_rpm').start()
        self.get_build = mock.patch('kojihub.get_build').start()
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
        with self.assertRaises(koji.GenericError):
            result = self.exports.getRPMHeaders(strict=False)
        with self.assertRaises(koji.GenericError):
            result = self.exports.getRPMHeaders(filepath='something')
        # we already test taskid without filepath above

    def test_unknown_rpm(self):
        self.get_rpm.return_value = None
        result = self.exports.getRPMHeaders(rpmID='FOO-1-1.noarch', strict=False)
        self.assertEqual(result, {})
        self.get_rpm.assert_called_with('FOO-1-1.noarch', strict=False)

        # again with strict mode
        self.get_rpm.side_effect = koji.GenericError('NO SUCH RPM')
        with self.assertRaises(koji.GenericError):
            result = self.exports.getRPMHeaders(rpmID='FOO-1-1.noarch', strict=True)
        self.get_rpm.assert_called_with('FOO-1-1.noarch', strict=True)
        self.get_build.assert_not_called()
        self.get_header_fields.assert_not_called()

    def test_external_rpm(self):
        self.get_rpm.return_value = {'external_repo_id': 1, 'id': 'RPMID'}
        result = self.exports.getRPMHeaders(rpmID='FOO-1-1.noarch', strict=False)
        self.assertEqual(result, {})

        # again with strict mode
        with self.assertRaises(koji.GenericError):
            result = self.exports.getRPMHeaders(rpmID='FOO-1-1.noarch', strict=True)
        self.get_build.assert_not_called()
        self.get_header_fields.assert_not_called()

    def test_deleted_build(self):
        self.get_rpm.return_value = {'build_id': 'BUILDID', 'external_repo_id': 0}
        self.get_build.return_value = {'nvr': 'NVR', 'state': koji.BUILD_STATES['DELETED']}
        result = self.exports.getRPMHeaders(rpmID='FOO-1-1.noarch', strict=False)
        self.assertEqual(result, {})
        self.get_build.assert_called_with('BUILDID', strict=True)

        # again with strict mode
        with self.assertRaises(koji.GenericError):
            result = self.exports.getRPMHeaders(rpmID='FOO-1-1.noarch', strict=True)
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
            result = self.exports.getRPMHeaders(rpmID='FOO-1-1.noarch', strict=True)
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

        with self.assertRaises(koji.GenericError):
            result = self.exports.getRPMHeaders(taskID=taskid, filepath=filepath, strict=True)

        self.get_rpm.assert_not_called()
        self.get_build.assert_not_called()
        self.get_header_fields.assert_not_called()
