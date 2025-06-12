import os
import shutil
import tempfile
import unittest

from unittest import mock

import koji
import kojihub


class TestAddVolume(unittest.TestCase):

    def setUp(self):
        # set up topdir
        self.tempdir = tempfile.mkdtemp()
        self.topdir = self.tempdir + '/koji'
        self.pathinfo = koji.PathInfo(self.topdir)
        mock.patch('koji.pathinfo', new=self.pathinfo).start()

        # set up test volume
        vol = self.tempdir + '/vol_test'
        self.volmount = vol
        toplink = vol + '/toplink'
        koji.ensuredir(vol)
        voldir = self.pathinfo.volumedir('test-volume')
        koji.ensuredir(os.path.dirname(voldir))  # koji/vol
        os.symlink(vol, voldir)
        os.symlink(self.topdir, toplink)

        self.verify_name_internal = mock.patch('kojihub.kojihub.verify_name_internal').start()
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name').start()
        # self.isdir = mock.patch('os.path.isdir').start()
        # self.pathinfo_volumedir = mock.patch('koji.pathinfo.volumedir').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.tempdir)

    def test_add_volume_wrong_format(self):
        volume_name = 'volume-name+'

        # name is longer as expected
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_volume(volume_name)

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_volume(volume_name)

    def test_non_exist_directory(self):
        volume_name = 'no-such-volume'

        with self.assertRaises(koji.GenericError) as cm:
            kojihub.add_volume(volume_name)

        self.assertEqual("please create the volume directory first", str(cm.exception))
        self.verify_name_internal.assert_called_once_with(volume_name)
        self.lookup_name.assert_not_called()

    def test_valid(self):
        volume_name = 'test-volume'
        volume_dict = {'id': 1, 'name': volume_name}
        self.lookup_name.return_value = volume_dict

        rv = kojihub.add_volume(volume_name, strict=False)

        self.assertEqual(rv, volume_dict)
        self.verify_name_internal.assert_called_once_with(volume_name)
        self.lookup_name.assert_called_once_with('volume', volume_name, strict=False, create=True)

    def test_volume_exists(self):
        volume_name = 'test-volume'
        volume_dict = {'id': 1, 'name': volume_name}
        self.lookup_name.return_value = volume_dict

        with self.assertRaises(koji.GenericError) as cm:
            kojihub.add_volume(volume_name, strict=True)

        self.assertEqual(f'volume {volume_name} already exists', str(cm.exception))
        self.verify_name_internal.assert_called_once_with(volume_name)
        self.lookup_name.assert_called_once_with('volume', volume_name, strict=False)

    def test_volume_broken_toplink(self):
        volume_name = 'test-volume'
        volume_dict = {'id': 1, 'name': volume_name}
        self.lookup_name.side_effect = [None, volume_dict]
        toplink = self.volmount + '/toplink'
        os.unlink(toplink)
        os.symlink('BROKEN-LINK', toplink)

        with self.assertRaises(koji.GenericError) as cm:
            kojihub.add_volume(volume_name, strict=True)

        assert str(cm.exception).startswith('Broken volume toplink')

    def test_volume_invalid_toplink(self):
        volume_name = 'test-volume'
        volume_dict = {'id': 1, 'name': volume_name}
        self.lookup_name.side_effect = [None, volume_dict]
        toplink = self.volmount + '/toplink'
        os.unlink(toplink)
        os.symlink('..', toplink)

        with self.assertRaises(koji.GenericError) as cm:
            kojihub.add_volume(volume_name, strict=True)

        assert str(cm.exception).startswith('Invalid volume toplink')

    def test_volume_nonlink_toplink(self):
        volume_name = 'test-volume'
        volume_dict = {'id': 1, 'name': volume_name}
        self.lookup_name.side_effect = [None, volume_dict]
        toplink = self.volmount + '/toplink'
        os.unlink(toplink)
        os.mkdir(toplink)

        with self.assertRaises(koji.GenericError) as cm:
            kojihub.add_volume(volume_name, strict=True)

        assert str(cm.exception).startswith('Not a symlink')

    def test_volume_create_toplink(self):
        # test that the toplink is automatically created if missing
        volume_name = 'test-volume'
        volume_dict = {'id': 1, 'name': volume_name}
        self.lookup_name.side_effect = [None, volume_dict]
        toplink = self.volmount + '/toplink'
        os.unlink(toplink)

        kojihub.add_volume(volume_name, strict=True)

        self.assertEqual(os.readlink(toplink), self.pathinfo.topdir)


# the end
