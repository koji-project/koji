from unittest import mock
import unittest

import koji
import kojihub


IP = kojihub.InsertProcessor


class FakeException(Exception):
    pass


class TestAddExternalRPM(unittest.TestCase):

    def setUp(self):
        self.get_rpm = mock.patch('kojihub.kojihub.get_rpm').start()
        self.get_external_repo_id = mock.patch('kojihub.kojihub.get_external_repo_id').start()
        self.nextval = mock.patch('kojihub.kojihub.nextval').start()
        self.Savepoint = mock.patch('kojihub.kojihub.Savepoint').start()
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.insert_execute = mock.MagicMock()

        self.rpminfo = {
            'name': 'NAME',
            'version': 'VERSION',
            'release': 'RELEASE',
            'epoch': None,
            'arch': 'noarch',
            'payloadhash': 'fakehash',
            'size': 42,
            'buildtime': 0,
        }
        self.repo = 'myrepo'

    def tearDown(self):
        mock.patch.stopall()

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = self.insert_execute
        self.inserts.append(insert)
        return insert

    def test_add_ext_rpm(self):
        self.get_rpm.return_value = None
        self.get_external_repo_id.return_value = mock.sentinel.repo_id
        self.nextval.return_value = mock.sentinel.rpm_id

        # call it
        kojihub.add_external_rpm(self.rpminfo, self.repo)

        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.data['external_repo_id'], mock.sentinel.repo_id)
        self.assertEqual(insert.data['id'], mock.sentinel.rpm_id)
        self.assertEqual(insert.table, 'rpminfo')

    def test_add_ext_rpm_bad_data(self):
        rpminfo = self.rpminfo.copy()
        del rpminfo['size']

        with self.assertRaises(koji.GenericError) as ex:
            kojihub.add_external_rpm(rpminfo, self.repo)
        self.assertEqual(f"size field missing: {rpminfo}", str(ex.exception))

        self.get_rpm.assert_not_called()
        self.nextval.assert_not_called()
        self.assertEqual(len(self.inserts), 0)

        rpminfo = self.rpminfo.copy()
        rpminfo['size'] = ['invalid type']

        with self.assertRaises(koji.GenericError) as ex:
            kojihub.add_external_rpm(rpminfo, self.repo)
        self.assertEqual(f"Invalid value for size: {rpminfo['size']}",
                         str(ex.exception))

        self.get_rpm.assert_not_called()
        self.nextval.assert_not_called()
        self.assertEqual(len(self.inserts), 0)

    def test_add_ext_rpm_dup(self):
        prev = self.rpminfo.copy()
        prev['external_repo_id'] = mock.sentinel.repo_id
        prev['external_repo_name'] = self.repo
        self.get_rpm.return_value = prev
        self.get_external_repo_id.return_value = mock.sentinel.repo_id

        # call it (default is strict)
        nvra = "%(name)s-%(version)s-%(release)s.%(arch)s" % self.rpminfo
        disp = f"{nvra}@{self.repo}"
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.add_external_rpm(self.rpminfo, self.repo)
        self.assertEqual(f"external rpm already exists: {disp}", str(ex.exception))

        self.assertEqual(len(self.inserts), 0)
        self.nextval.assert_not_called()

        # call it without strict
        ret = kojihub.add_external_rpm(self.rpminfo, self.repo, strict=False)

        self.assertEqual(ret, self.get_rpm.return_value)
        self.assertEqual(len(self.inserts), 0)
        self.nextval.assert_not_called()

        # different hash
        prev['payloadhash'] = 'different hash'
        nvra = "%(name)s-%(version)s-%(release)s.%(arch)s" % self.rpminfo
        disp = f"{nvra}@{self.repo}"
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.add_external_rpm(self.rpminfo, self.repo, strict=False)
        self.assertEqual(f"hash changed for external rpm: {disp} (different hash -> fakehash)",
                         str(ex.exception))

        self.assertEqual(len(self.inserts), 0)
        self.nextval.assert_not_called()

    def test_add_ext_rpm_dup_late(self):
        prev = self.rpminfo.copy()
        prev['external_repo_id'] = mock.sentinel.repo_id
        prev['external_repo_name'] = self.repo
        self.get_rpm.side_effect = [None, prev]
        self.get_external_repo_id.return_value = mock.sentinel.repo_id
        self.insert_execute.side_effect = FakeException('insert failed')

        # call it (default is strict)
        nvra = "%(name)s-%(version)s-%(release)s.%(arch)s" % self.rpminfo
        disp = f"{nvra}@{self.repo}"
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.add_external_rpm(self.rpminfo, self.repo)
        self.assertEqual(f"external rpm already exists: {disp}", str(ex.exception))

        self.assertEqual(len(self.inserts), 1)
        self.nextval.assert_called_once()

        # call it without strict
        self.inserts[:] = []
        self.nextval.reset_mock()
        self.get_rpm.side_effect = [None, prev]
        ret = kojihub.add_external_rpm(self.rpminfo, self.repo, strict=False)

        self.assertEqual(ret, prev)
        self.assertEqual(len(self.inserts), 1)
        self.nextval.assert_called_once()

        # different hash
        self.inserts[:] = []
        self.nextval.reset_mock()
        self.get_rpm.side_effect = [None, prev]
        prev['payloadhash'] = 'different hash'
        nvra = "%(name)s-%(version)s-%(release)s.%(arch)s" % self.rpminfo
        disp = f"{nvra}@{self.repo}"
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.add_external_rpm(self.rpminfo, self.repo, strict=False)
        self.assertEqual(f"hash changed for external rpm: {disp} (different hash -> fakehash)",
                         str(ex.exception))

        self.assertEqual(len(self.inserts), 1)
        self.nextval.assert_called_once()

        # no dup after failed insert
        self.inserts[:] = []
        self.nextval.reset_mock()
        self.get_rpm.side_effect = [None, None]
        with self.assertRaises(FakeException) as ex:
            kojihub.add_external_rpm(self.rpminfo, self.repo, strict=False)
        self.assertEqual('insert failed', str(ex.exception))

        self.assertEqual(len(self.inserts), 1)
        self.nextval.assert_called_once()
