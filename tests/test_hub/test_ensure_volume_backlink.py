from unittest import mock
import os
import os.path
import shutil
import tempfile
import unittest
import koji
import kojihub

import pytest

class TestEnsureVolumeBacklink(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.topdir = self.tempdir + '/koji'
        self.pathinfo = koji.PathInfo(self.topdir)
        mock.patch('koji.pathinfo', new=self.pathinfo).start()

        # set up other volume
        vol = self.tempdir + '/vol_other'
        self.volmount = vol
        toplink = vol + '/toplink'
        koji.ensuredir(vol)
        voldir = self.pathinfo.volumedir('OTHER')
        koji.ensuredir(os.path.dirname(voldir))  # koji/vol
        os.symlink(vol, voldir)
        os.symlink(self.topdir, toplink)

        # mock.patch('kojihub.kojihub.lookup_name', new=self.my_lookup_name).start()
        self.buildinfo = {
                'id': 137,
                'task_id': 'TASK_ID',
                'name': 'some-image',
                'version': '1.2.3.4',
                'release': '3',
                'epoch': None,
                'source': None,
                'state': koji.BUILD_STATES['BUILDING'],
                # 'volume_id': 1,
                'volume_name': 'OTHER',
                }

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.tempdir)

    def my_lookup_name(self, table, info, **kw):
        if table != 'volume':
            raise Exception("Cannot fake call")
        return {
                'id': 'VOLUMEID:%s' % info,
                'name': '%s' % info,
                }

    def test_volume_symlink_no_action(self):
        # the call should do nothing if the volume is DEFAULT
        binfo = self.buildinfo.copy()
        binfo['volume_name'] = 'DEFAULT'
        files1 = list(find_files(self.topdir))

        kojihub.ensure_volume_backlink(binfo)

        files2 = list(find_files(self.topdir))
        self.assertEqual(files1, files2)

    def test_volume_symlink_create(self):
        # verify that backlink is created correctly
        basedir = self.pathinfo.build(self.buildinfo)  # OTHER volume

        kojihub.ensure_volume_backlink(self.buildinfo)

        files = list(find_files(self.volmount))
        expected = [
                'packages',
                'toplink',
                'packages/some-image',
                'packages/some-image/1.2.3.4',
                'packages/some-image/1.2.3.4/3',
                ]
        self.assertEqual(files, expected)
        relpath = ('../../../toplink/packages/'
                   '%(name)s/%(version)s/%(release)s' % self.buildinfo)
        self.assertEqual(os.readlink(basedir), relpath)

    def test_volume_symlink_exists(self):
        # if an incorrect link is present, it should be replaced
        basedir = self.pathinfo.build(self.buildinfo)  # OTHER volume
        oldpath = 'some/other/link'
        os.makedirs(os.path.dirname(basedir))
        os.symlink(oldpath, basedir)

        kojihub.ensure_volume_backlink(self.buildinfo)

        relpath = ('../../../toplink/packages/'
                   '%(name)s/%(version)s/%(release)s' % self.buildinfo)
        self.assertEqual(os.readlink(basedir), relpath)

    def test_volume_symlink_exists_same(self):
        # if link is already correct, it should be left alone
        basedir = self.pathinfo.build(self.buildinfo)  # OTHER volume
        relpath = ('../../../toplink/packages/'
                   '%(name)s/%(version)s/%(release)s' % self.buildinfo)
        os.makedirs(os.path.dirname(basedir))
        os.symlink(relpath, basedir)

        with mock.patch('os.unlink') as unlink:
            kojihub.ensure_volume_backlink(self.buildinfo)
            unlink.assert_not_called()

        files = list(find_files(self.volmount))
        expected = [
                'packages',
                'toplink',
                'packages/some-image',
                'packages/some-image/1.2.3.4',
                'packages/some-image/1.2.3.4/3',
                ]
        self.assertEqual(files, expected)

    def test_volume_symlink_exists_error(self):
        # if the path exists and is not a link, we should error
        basedir = self.pathinfo.build(self.buildinfo)  # OTHER volume
        os.makedirs(basedir)
        files1 = list(find_files(self.tempdir))

        with self.assertRaises(koji.GenericError):
            kojihub.ensure_volume_backlink(self.buildinfo)

        files2 = list(find_files(self.tempdir))
        self.assertEqual(files1, files2)

    def test_volume_symlink_exists_error(self):
        # if the volume dir is bad, we should error
        basedir = self.pathinfo.build(self.buildinfo)  # OTHER volume

        os.unlink(self.volmount + '/toplink')
        with self.assertRaises(koji.GenericError):
            kojihub.ensure_volume_backlink(self.buildinfo)

        os.rmdir(self.volmount)
        with self.assertRaises(koji.GenericError):
            kojihub.ensure_volume_backlink(self.buildinfo)


def find_files(dirpath):
    '''Find all files under dir, report relative paths'''
    for path, dirs, files in os.walk(dirpath):
        for fn in sorted(dirs + files):
            yield os.path.relpath(os.path.join(path, fn), dirpath)
