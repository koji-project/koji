import os
import mock
import shutil
import tempfile
import unittest

import kojihub
from koji import GenericError


class TestGetUploadPath(unittest.TestCase):

    def setUp(self):
        self.topdir = tempfile.mkdtemp()
        mock.patch('koji.pathinfo._topdir', new=self.topdir).start()

    def tearDown(self):
        shutil.rmtree(self.topdir)
        mock.patch.stopall()

    def test_get_upload_path_invalid_filename(self):
        with self.assertRaises(GenericError):
            kojihub.get_upload_path(reldir='', name='. error')

    def test_get_upload_path_invalid_upload_dir_1(self):
        with self.assertRaises(GenericError):
            kojihub.get_upload_path(reldir='..', name='error')

    def test_get_upload_path_invalid_upload_dir_2(self):
        with self.assertRaises(GenericError):
            kojihub.get_upload_path(reldir='tasks/1', name='error', create=True)

    def test_get_upload_path_invalid_upload_dir_3(self):
        with self.assertRaises(GenericError):
            kojihub.get_upload_path(reldir='tasks/1/should_be_number', name='error', create=True)

    @mock.patch('kojihub.context')
    @mock.patch('kojihub.Host')
    def test_get_upload_path_invalid_upload_dir_owner(self, host, context):
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor
        reldir = 'fake/1/1'
        fullpath = '%s/work/%s' % (self.topdir, reldir)
        os.makedirs(fullpath)

        with open('{0}/.user'.format(fullpath), 'wt') as f:
            f.write('1')

        with self.assertRaises(GenericError):
            kojihub.get_upload_path(reldir=reldir, name='error', create=True)

    @mock.patch('kojihub.Host')
    def test_get_upload_path_invalid_upload_no_dir_owner(self, host):
        dir = kojihub.get_upload_path(reldir='tasks/1/1', name='error', create=False)
        assert dir == '%s/work/tasks/1/1/error' % self.topdir

