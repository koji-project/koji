from __future__ import absolute_import
import os
import mock
import shutil
import unittest
import kojihub
from koji import GenericError


class TestGetUploadPath(unittest.TestCase):


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
    @mock.patch('koji.pathinfo.work')
    @mock.patch('kojihub.Host')
    def test_get_upload_path_invalid_upload_dir_owner(self, host, work, context):
        work.return_value = '/tmp'
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor
        reldir = 'fake/1/1'
        fullpath = '{0}/{1}'.format(work.return_value, reldir)
        os.makedirs(fullpath)

        with open('{0}/.user'.format(fullpath), 'wb') as f:
            f.write('1')

        with self.assertRaises(GenericError):
            kojihub.get_upload_path(reldir=reldir, name='error', create=True)

        shutil.rmtree('/tmp/fake')

    @mock.patch('koji.pathinfo.work')
    @mock.patch('kojihub.Host')
    def test_get_upload_path_invalid_upload_no_dir_owner(self, host, work):
        work.return_value = '/tmp'
        dir = kojihub.get_upload_path(reldir='tasks/1/1', name='error', create=False)
        assert dir == '/tmp/tasks/1/1/error'

