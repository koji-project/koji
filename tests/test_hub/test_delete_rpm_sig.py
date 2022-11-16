import unittest

import mock

import koji
import kojihub

DP = kojihub.DeleteProcessor


class TestDeleteRPMSig(unittest.TestCase):

    def getDelete(self, *args, **kwargs):
        delete = DP(*args, **kwargs)
        delete.execute = mock.MagicMock()
        self.deletes.append(delete)
        return delete

    def setUp(self):
        self.DeleteProcessor = mock.patch('kojihub.DeleteProcessor',
                                          side_effect=self.getDelete).start()
        self.deletes = []
        self.get_rpm = mock.patch('kojihub.get_rpm').start()
        self.query_rpm_sigs = mock.patch('kojihub.query_rpm_sigs').start()
        self.get_build = mock.patch('kojihub.get_build').start()
        self.get_user = mock.patch('kojihub.get_user').start()
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

    def tearDown(self):
        mock.patch.stopall()

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
        rinfo = {'external_repo_id': 1, 'external_repo_name': 'INTERNAL'}
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

    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('os.remove')
    def test_file_not_found_error(self, os_remove, pb):
        rpminfo = 2
        os_remove.side_effect = FileNotFoundError()
        self.get_rpm.return_value = self.rinfo
        self.get_build.return_value = self.buildinfo
        self.get_user.return_value = self.userinfo
        self.query_rpm_sigs.return_value = self.queryrpmsigs
        r = kojihub.delete_rpm_sig(rpminfo, sigkey='testkey')
        self.assertEqual(r, None)
        delete = self.deletes[0]
        self.assertEqual(delete.table, 'rpmsigs')
        self.assertEqual(delete.clauses, ["rpm_id=%(rpm_id)i", "sigkey=%(sigkey)s"])
        self.get_rpm.assert_called_once_with(rpminfo, strict=True)
        self.query_rpm_sigs.assert_called_once_with(rpm_id=self.rinfo['id'], sigkey='testkey')
        self.get_build.assert_called_once_with(self.rinfo['build_id'])

    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('os.remove', side_effect=OSError)
    def test_not_valid(self, os_remove, pb):
        rpminfo = 2
        filepath = 'fakebuildpath/data/signed/x86_64/fs_mark-3.3-20.el8.x86_64.rpm'
        self.get_rpm.return_value = self.rinfo
        self.get_build.return_value = self.buildinfo
        self.query_rpm_sigs.return_value = self.queryrpmsigs
        expected_msg = "File %s cannot be deleted." % filepath
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.delete_rpm_sig(rpminfo, all_sigs=True)
        self.assertEqual(ex.exception.args[0], expected_msg)
        delete = self.deletes[0]
        self.assertEqual(delete.table, 'rpmsigs')
        self.assertEqual(delete.clauses, ["rpm_id=%(rpm_id)i"])
        self.get_rpm.assert_called_once_with(rpminfo, strict=True)
        self.query_rpm_sigs.assert_called_once_with(rpm_id=self.rinfo['id'], sigkey=None)
        self.get_build.assert_called_once_with(self.rinfo['build_id'])

    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('os.remove')
    def test_valid(self, os_remove, pb):
        rpminfo = 2
        self.get_rpm.return_value = self.rinfo
        self.get_build.return_value = self.buildinfo
        self.get_user.return_value = self.userinfo
        self.query_rpm_sigs.return_value = self.queryrpmsigs
        kojihub.delete_rpm_sig(rpminfo, all_sigs=True)
        self.assertEqual(len(self.deletes), 1)
        delete = self.deletes[0]
        self.assertEqual(delete.table, 'rpmsigs')
        self.assertEqual(delete.clauses, ["rpm_id=%(rpm_id)i"])
        self.get_rpm.assert_called_once_with(rpminfo, strict=True)
        self.query_rpm_sigs.assert_called_once_with(rpm_id=self.rinfo['id'], sigkey=None)
        self.get_build.assert_called_once_with(self.rinfo['build_id'])
