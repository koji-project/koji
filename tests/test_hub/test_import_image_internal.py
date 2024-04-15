import mock
import os
import shutil
import tempfile
import unittest

import kojihub


class TestImportImageInternal(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context_db = mock.patch('kojihub.db.context').start()
        self.Task = mock.patch('kojihub.kojihub.Task').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.get_archive_type = mock.patch('kojihub.kojihub.get_archive_type').start()
        self.path_work = mock.patch('koji.pathinfo.work').start()
        self.import_archive = mock.patch('kojihub.kojihub.import_archive').start()
        self.build = mock.patch('koji.pathinfo.build').start()
        self.get_rpm = mock.patch('kojihub.kojihub.get_rpm').start()

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        mock.patch.stopall()

    def test_basic(self):
        task = mock.MagicMock()
        task.assertHost = mock.MagicMock()
        self.Task.return_value = task
        imgdata = {
            'arch': 'x86_64',
            'task_id': 1,
            'files': [
                'some_file',
            ],
            'rpmlist': [
            ],
        }
        cursor = mock.MagicMock()
        self.context_db.cnx.cursor.return_value = cursor
        self.context_db.session.host_id = 42
        self.get_build.return_value = {
            'id': 2,
            'name': 'name',
            'version': 'version',
            'release': 'release',
        }
        self.get_archive_type.return_value = 4
        self.path_work.return_value = self.tempdir
        os.makedirs(self.tempdir + "/tasks/1/1")
        kojihub.importImageInternal(
            task_id=1, build_info=self.get_build.return_value, imgdata=imgdata)

    def test_with_rpm(self):
        task = mock.MagicMock()
        task.assertHost = mock.MagicMock()
        self.Task.return_value = task
        rpm = {
            # 'location': 'foo',
            'id': 6,
            'name': 'foo',
            'version': '3.1',
            'release': '2',
            'epoch': 0,
            'arch': 'noarch',
            'payloadhash': 'laksjdflkasjdf',
            'size': 42,
            'buildtime': 12345,
        }
        imgdata = {
            'arch': 'x86_64',
            'task_id': 1,
            'files': [
                'some_file',
            ],
            'rpmlist': [rpm],
        }
        build_info = {
            'name': 'name',
            'version': 'version',
            'release': 'release',
            'id': 2
        }
        cursor = mock.MagicMock()
        self.context_db.cnx.cursor.return_value = cursor
        self.context_db.session.host_id = 42
        self.get_build.return_value = build_info
        self.get_rpm.return_value = rpm
        self.get_archive_type.return_value = 4
        self.path_work.return_value = self.tempdir
        self.build.return_value = self.tempdir
        self.import_archive.return_value = {
            'id': 9,
            'filename': self.tempdir + '/foo.archive',
        }
        workdir = self.tempdir + "/tasks/1/1"
        os.makedirs(workdir)
        # Create a log file to exercise that code path
        with open(workdir + '/foo.log', 'w'):
            pass

        kojihub.importImageInternal(task_id=1, build_info=build_info, imgdata=imgdata)

        # Check that the log symlink made it to where it was supposed to.
        dest = os.readlink(workdir + '/foo.log')
        dest = os.path.abspath(os.path.join(workdir, dest))
        self.assertEqual(dest, self.tempdir + '/data/logs/image/x86_64/foo.log')

        # And.. check all the sql statements
        self.assertEqual(len(cursor.execute.mock_calls), 1)
        expression, kwargs = cursor.execute.mock_calls[0][1]
        expression = " ".join(expression.split())
        expected = 'INSERT INTO archive_rpm_components (archive_id, rpm_id) ' + \
            'VALUES (%(archive_id0)s, %(rpm_id0)s)'
        self.assertEqual(expression, expected)
        self.assertEqual(kwargs, {'archive_id0': 9, 'rpm_id0': 6})
