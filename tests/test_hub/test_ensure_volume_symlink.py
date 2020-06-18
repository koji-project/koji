import mock
import os
import os.path
import shutil
import tempfile
import unittest
import koji
import kojihub


class TestEnsureVolumeSymlink(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.pathinfo = koji.PathInfo(self.tempdir)
        mock.patch('koji.pathinfo', new=self.pathinfo).start()
        mock.patch('kojihub.lookup_name', new=self.my_lookup_name).start()
        self.check_volume_policy = mock.patch('kojihub.check_volume_policy',
                return_value={'id':0, 'name': 'DEFAULT'}).start()
        self.buildinfo = {
                'id': 137,
                'task_id': 'TASK_ID',
                'name': 'some-image',
                'version': '1.2.3.4',
                'release': '3',
                'epoch': None,
                'source': None,
                'state': koji.BUILD_STATES['BUILDING'],
                'volume_id': 0,
                'volume_name': 'DEFAULT',
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
        kojihub.ensure_volume_symlink(self.buildinfo)
        if os.listdir(self.tempdir):
            raise Exception('call created unexpected files')

        del self.buildinfo['volume_name']
        with mock.patch('kojihub.logger') as logger:
            kojihub.ensure_volume_symlink(self.buildinfo)
            logger.warning.assert_called_once()

    def test_volume_symlink_create(self):
        basedir = self.pathinfo.build(self.buildinfo)  # default volume
        self.buildinfo['volume_name'] = 'test'
        self.buildinfo['volume_id'] = 1
        kojihub.ensure_volume_symlink(self.buildinfo)
        files = list(find_files(self.tempdir))
        expected = [
                'packages',
                'packages/some-image',
                'packages/some-image/1.2.3.4',
                'packages/some-image/1.2.3.4/3',
                ]
        self.assertEqual(files, expected)
        relpath = ('../../../vol/test/packages/'
                '%(name)s/%(version)s/%(release)s' % self.buildinfo)
        self.assertEqual(os.readlink(basedir), relpath)


    def test_volume_symlink_exists(self):
        basedir = self.pathinfo.build(self.buildinfo)  # default volume
        oldpath = 'some/other/link'
        os.makedirs(os.path.dirname(basedir))
        os.symlink(oldpath, basedir)
        self.buildinfo['volume_name'] = 'test'
        self.buildinfo['volume_id'] = 1
        kojihub.ensure_volume_symlink(self.buildinfo)
        relpath = ('../../../vol/test/packages/'
                '%(name)s/%(version)s/%(release)s' % self.buildinfo)
        self.assertEqual(os.readlink(basedir), relpath)

    def test_volume_symlink_exists_same(self):
        basedir = self.pathinfo.build(self.buildinfo)  # default volume
        relpath = ('../../../vol/test/packages/'
                '%(name)s/%(version)s/%(release)s' % self.buildinfo)
        os.makedirs(os.path.dirname(basedir))
        os.symlink(relpath, basedir)
        self.buildinfo['volume_name'] = 'test'
        self.buildinfo['volume_id'] = 1
        with mock.patch('os.unlink') as unlink:
            kojihub.ensure_volume_symlink(self.buildinfo)
            unlink.assert_not_called()
        files = list(find_files(self.tempdir))
        expected = [
                'packages',
                'packages/some-image',
                'packages/some-image/1.2.3.4',
                'packages/some-image/1.2.3.4/3',
                ]
        self.assertEqual(files, expected)

    def test_volume_symlink_exists_error(self):
        basedir = self.pathinfo.build(self.buildinfo)  # default volume
        # create default volume dir, should trigger an error
        os.makedirs(basedir)
        self.buildinfo['volume_name'] = 'test'
        self.buildinfo['volume_id'] = 1
        with self.assertRaises(koji.GenericError):
            kojihub.ensure_volume_symlink(self.buildinfo)
        files = list(find_files(self.tempdir))
        expected = [
                'packages',
                'packages/some-image',
                'packages/some-image/1.2.3.4',
                'packages/some-image/1.2.3.4/3',
                ]
        self.assertEqual(files, expected)


def find_files(dirpath):
    '''Find all files under dir, report relative paths'''
    for path, dirs, files in os.walk(dirpath):
        for fn in sorted(dirs + files):
            yield os.path.relpath(os.path.join(path, fn), dirpath)
