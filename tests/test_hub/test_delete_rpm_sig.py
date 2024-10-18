import os
import tempfile
import shutil
import unittest

from unittest import mock

import koji
import kojihub
from koji.util import joinpath

DP = kojihub.DeleteProcessor


class TestDeleteRPMSig(unittest.TestCase):

    def getDelete(self, *args, **kwargs):
        delete = DP(*args, **kwargs)
        delete.execute = mock.MagicMock()
        self.deletes.append(delete)
        return delete

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.pathinfo = koji.PathInfo(self.tempdir)
        mock.patch('koji.pathinfo', new=self.pathinfo).start()
        self.DeleteProcessor = mock.patch('kojihub.kojihub.DeleteProcessor',
                                          side_effect=self.getDelete).start()
        self.deletes = []
        self.get_rpm = mock.patch('kojihub.kojihub.get_rpm').start()
        self.query_rpm_sigs = mock.patch('kojihub.kojihub.query_rpm_sigs').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.buildinfo = {'build_id': 1,
                          'epoch': None,
                          'extra': None,
                          'id': 1,
                          'name': 'fs_mark',
                          'nvr': 'fs_mark-3.3-20.el8',
                          'owner_id': 1,
                          'owner_name': 'kojiadmin',
                          'package_id': 1,
                          'package_name': 'fs_mark',
                          'release': '20.el8',
                          'state': 1,
                          'task_id': None,
                          'version': '3.3'}
        self.rinfo = {'arch': 'x86_64',
                      'build_id': 1,
                      'buildroot_id': None,
                      'buildtime': 1564782768,
                      'epoch': None,
                      'external_repo_id': None,
                      'extra': None,
                      'id': 2,
                      'metadata_only': False,
                      'name': 'fs_mark',
                      'payloadhash': 'ed0690ab4b0508f2448d99a08e0a004a',
                      'release': '20.el8',
                      'size': 25644,
                      'version': '3.3'}
        self.queryrpmsigs = [{'rpm_id': 2, 'sighash': 'cb4d01bd3671b41ef51abc9be851e614',
                              'sigkey': ''},
                             {'rpm_id': 2, 'sighash': '78c245caa6deb70f0abc8b844c642cd6',
                              'sigkey': '2f86d6a1'}]
        self.userinfo = {'authtype': 2, 'id': 1, 'krb_principal': None, 'krb_principals': [],
                         'name': 'testuser', 'status': 0, 'usertype': 0}
        self.set_up_files()

    def set_up_files(self):
        builddir = self.pathinfo.build(self.buildinfo)
        os.makedirs(builddir)
        self.builddir = builddir
        self.signed = {}
        self.sighdr = {}
        for sig in self.queryrpmsigs:
            key = sig['sigkey']
            signed = joinpath(builddir, self.pathinfo.signed(self.rinfo, key))
            self.signed[key] = signed
            koji.ensuredir(os.path.dirname(signed))
            with open(signed, 'wt') as fo:
                fo.write('SIGNED COPY\n')

            sighdr = joinpath(builddir, self.pathinfo.sighdr(self.rinfo, key))
            self.sighdr[key] = sighdr
            koji.ensuredir(os.path.dirname(sighdr))
            with open(sighdr, 'wt') as fo:
                fo.write('DETACHED SIGHDR\n')

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.tempdir)

    def test_rpm_not_existing(self):
        rpm_id = 1234
        expected_msg = 'No such rpm: %s' % rpm_id
        self.get_rpm.side_effect = koji.GenericError("No such rpm: %s" % rpm_id)
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.delete_rpm_sig(rpm_id, all_sigs=True)
        self.assertEqual(len(self.deletes), 0)
        self.assertEqual(ex.exception.args[0], expected_msg)
        self.get_rpm.assert_called_once_with(rpm_id, strict=True)
        self.query_rpm_sigs.assert_not_called()

    def test_not_all_sig_and_not_sigkey(self):
        expected_msg = 'No signature specified'
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.delete_rpm_sig(1234)
        self.assertEqual(len(self.deletes), 0)
        self.assertEqual(ex.exception.args[0], expected_msg)
        self.get_rpm.assert_not_called()
        self.query_rpm_sigs.assert_not_called()

    def test_external_repo(self):
        rpminfo = 1234
        rinfo = self.rinfo.copy()
        rinfo.update({'external_repo_id': 1, 'external_repo_name': 'INTERNAL'})
        self.get_rpm.return_value = rinfo
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.delete_rpm_sig(rpminfo, all_sigs=True)
        self.assertEqual(len(self.deletes), 0)
        expected_msg = "Not an internal rpm: %s (from %s)" % (rpminfo, rinfo['external_repo_name'])
        self.assertEqual(ex.exception.args[0], expected_msg)
        self.get_rpm.assert_called_once_with(rpminfo, strict=True)
        self.query_rpm_sigs.assert_not_called()

    def test_empty_query_sign(self):
        rpminfo = 1234
        nvra = "%s-%s-%s.%s" % (self.rinfo['name'], self.rinfo['version'], self.rinfo['release'],
                                self.rinfo['arch'])
        expected_msg = "%s has no matching signatures to delete" % nvra
        self.get_rpm.return_value = self.rinfo
        self.query_rpm_sigs.return_value = []
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.delete_rpm_sig(rpminfo, all_sigs=True)
        self.assertEqual(len(self.deletes), 0)
        self.assertEqual(ex.exception.args[0], expected_msg)
        self.get_rpm.assert_called_once_with(rpminfo, strict=True)
        self.query_rpm_sigs.assert_called_once_with(rpm_id=self.rinfo['id'], sigkey=None)

    def test_file_not_found_error(self):
        rpminfo = self.rinfo['id']
        self.get_rpm.return_value = self.rinfo
        self.get_build.return_value = self.buildinfo
        self.get_user.return_value = self.userinfo
        self.query_rpm_sigs.return_value = self.queryrpmsigs

        # a missing signed copy or header should not error
        builddir = self.pathinfo.build(self.buildinfo)
        sigkey = '2f86d6a1'
        os.remove(self.signed[sigkey])
        os.remove(self.sighdr[sigkey])
        r = kojihub.delete_rpm_sig(rpminfo, sigkey='testkey')
        self.assertEqual(r, None)

        # the files should still be gone
        for sigkey in self.signed:
            if os.path.exists(self.signed[sigkey]):
                raise Exception('signed copy not deleted')
        for sigkey in self.sighdr:
            if os.path.exists(self.sighdr[sigkey]):
                raise Exception('header still in place')

        self.assertEqual(len(self.deletes), 2)
        delete = self.deletes[0]
        self.assertEqual(delete.table, 'rpmsigs')
        self.assertEqual(delete.clauses, ["rpm_id=%(rpm_id)s", "sigkey IN %(found_keys)s"])

        delete = self.deletes[1]
        self.assertEqual(delete.table, 'rpm_checksum')
        self.assertEqual(delete.clauses, ["rpm_id=%(rpm_id)s", "sigkey IN %(found_keys)s"])
        self.get_rpm.assert_called_once_with(rpminfo, strict=True)
        self.query_rpm_sigs.assert_called_once_with(rpm_id=self.rinfo['id'], sigkey='testkey')
        self.get_build.assert_called_once_with(self.rinfo['build_id'], strict=True)

    def test_header_not_a_file(self):
        rpminfo = self.rinfo['id']
        self.get_rpm.return_value = self.rinfo
        self.get_build.return_value = self.buildinfo
        self.get_user.return_value = self.userinfo
        self.query_rpm_sigs.return_value = self.queryrpmsigs

        # we should error, without making any changes, if a header is not a regular file
        builddir = self.pathinfo.build(self.buildinfo)
        bad_sigkey = '2f86d6a1'
        bad_hdr= self.sighdr[bad_sigkey]
        os.remove(bad_hdr)
        os.mkdir(bad_hdr)
        with self.assertRaises(koji.GenericError) as ex:
            r = kojihub.delete_rpm_sig(rpminfo, sigkey='testkey')
        expected_msg = "Not a regular file: %s" % bad_hdr
        self.assertEqual(ex.exception.args[0], expected_msg)

        # the files should still be there
        for sigkey in self.signed:
            if not os.path.exists(self.signed[sigkey]):
                raise Exception('signed copy was deleted')
        for sigkey in self.sighdr:
            if not os.path.exists(self.sighdr[sigkey]):
                raise Exception('header was deleted')
        if not os.path.isdir(bad_hdr):
            # the function should not have touched the invalid path
            raise Exception('bad header file was removed')

    def test_stray_backup(self):
        rpminfo = self.rinfo['id']
        self.get_rpm.return_value = self.rinfo
        self.get_build.return_value = self.buildinfo
        self.get_user.return_value = self.userinfo
        self.query_rpm_sigs.return_value = self.queryrpmsigs

        siginfo = self.queryrpmsigs[0]
        sigkey = siginfo['sigkey']
        backup = "%s.%s.save" % (self.sighdr[sigkey], siginfo['sighash'])
        with open(backup, 'wt') as fo:
            fo.write('STRAY FILE\n')
            # different contents
        with self.assertRaises(koji.GenericError) as ex:
            r = kojihub.delete_rpm_sig(rpminfo, sigkey='testkey')
        expected_msg = "Stray header backup file: %s" % backup
        self.assertEqual(ex.exception.args[0], expected_msg)
        # files should not have been removed
        for sigkey in self.signed:
            if not os.path.exists(self.signed[sigkey]):
                raise Exception('signed copy was deleted incorrectly')
        for sigkey in self.sighdr:
            if not os.path.exists(self.sighdr[sigkey]):
                raise Exception('header was deleted incorrectly')

    def test_dup_backup(self):
        rpminfo = self.rinfo['id']
        self.get_rpm.return_value = self.rinfo
        self.get_build.return_value = self.buildinfo
        self.get_user.return_value = self.userinfo
        self.query_rpm_sigs.return_value = self.queryrpmsigs

        siginfo = self.queryrpmsigs[0]
        sigkey = siginfo['sigkey']
        backup = "%s.%s.save" % (self.sighdr[sigkey], siginfo['sighash'])
        with open(backup, 'wt') as fo:
            fo.write('DETACHED SIGHDR\n')
            # SAME contents

        r = kojihub.delete_rpm_sig(rpminfo, sigkey='testkey')

        # the files should be gone
        for sigkey in self.signed:
            if os.path.exists(self.signed[sigkey]):
                raise Exception('signed copy not deleted')
        for sigkey in self.sighdr:
            if os.path.exists(self.sighdr[sigkey]):
                raise Exception('header still in place')

        # the sighdrs should be saved
        for siginfo in self.queryrpmsigs:
            sigkey = siginfo['sigkey']
            backup = "%s.%s.save" % (self.sighdr[sigkey], siginfo['sighash'])
            with open(backup, 'rt') as fo:
                self.assertEqual(fo.read(), 'DETACHED SIGHDR\n')

    @mock.patch('os.remove', side_effect=OSError)
    def test_not_valid(self, os_remove):
        rpminfo = 2
        filepath = '%s/packages/fs_mark/3.3/20.el8/data/signed/x86_64/fs_mark-3.3-20.el8.x86_64.rpm' % self.tempdir
        self.get_rpm.return_value = self.rinfo
        self.get_build.return_value = self.buildinfo
        self.query_rpm_sigs.return_value = self.queryrpmsigs
        expected_msg = "Failed to delete %s" % filepath
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.delete_rpm_sig(rpminfo, all_sigs=True)
        self.assertEqual(ex.exception.args[0], expected_msg)

        self.assertEqual(len(self.deletes), 2)
        delete = self.deletes[0]
        self.assertEqual(delete.table, 'rpmsigs')
        self.assertEqual(delete.clauses, ["rpm_id=%(rpm_id)s", "sigkey IN %(found_keys)s"])

        delete = self.deletes[1]
        self.assertEqual(delete.table, 'rpm_checksum')
        self.assertEqual(delete.clauses, ["rpm_id=%(rpm_id)s", "sigkey IN %(found_keys)s"])
        self.get_rpm.assert_called_once_with(rpminfo, strict=True)
        self.query_rpm_sigs.assert_called_once_with(rpm_id=self.rinfo['id'], sigkey=None)
        self.get_build.assert_called_once_with(self.rinfo['build_id'], strict=True)

    def test_valid(self):
        rpminfo = 2
        self.get_rpm.return_value = self.rinfo
        self.get_build.return_value = self.buildinfo
        self.get_user.return_value = self.userinfo
        self.query_rpm_sigs.return_value = self.queryrpmsigs
        kojihub.delete_rpm_sig(rpminfo, all_sigs=True)

        # the files should be gone
        for sigkey in self.signed:
            if os.path.exists(self.signed[sigkey]):
                raise Exception('signed copy not deleted')
        for sigkey in self.sighdr:
            if os.path.exists(self.sighdr[sigkey]):
                raise Exception('header still in place')

        # the sighdrs should be saved
        for siginfo in self.queryrpmsigs:
            sigkey = siginfo['sigkey']
            backup = "%s.%s.save" % (self.sighdr[sigkey], siginfo['sighash'])
            with open(backup, 'rt') as fo:
                self.assertEqual(fo.read(), 'DETACHED SIGHDR\n')

        self.assertEqual(len(self.deletes), 2)
        delete = self.deletes[0]
        self.assertEqual(delete.table, 'rpmsigs')
        self.assertEqual(delete.clauses, ["rpm_id=%(rpm_id)s", "sigkey IN %(found_keys)s"])

        delete = self.deletes[1]
        self.assertEqual(delete.table, 'rpm_checksum')
        self.assertEqual(delete.clauses, ["rpm_id=%(rpm_id)s", "sigkey IN %(found_keys)s"])
        self.get_rpm.assert_called_once_with(rpminfo, strict=True)
        self.query_rpm_sigs.assert_called_once_with(rpm_id=self.rinfo['id'], sigkey=None)
        self.get_build.assert_called_once_with(self.rinfo['build_id'], strict=True)
