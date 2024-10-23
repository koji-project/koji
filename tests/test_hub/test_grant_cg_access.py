# coding: utf-8
import unittest
from unittest import mock

import koji
import kojihub

IP = kojihub.InsertProcessor


class TestGrantCGAccess(unittest.TestCase):

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        insert.make_create = mock.MagicMock()
        insert.dup_check = self.ins_dup_check
        self.inserts.append(insert)
        return insert

    def setUp(self):
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.ins_dup_check = mock.MagicMock()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_without_create(self):
        self.ins_dup_check.return_value = False
        cg = {'id': 11, 'name': 'test-cg-name'}
        user = {'id': 123, 'name': 'testuser'}
        self.get_user.return_value = user
        self.lookup_name.return_value = cg
        kojihub.grant_cg_access(user['name'], cg['name'])

        # check the insert
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'cg_users')
        self.assertEqual(insert.data, {'cg_id': cg['id'], 'user_id': user['id']})
        self.assertEqual(insert.rawdata, {})
        self.get_user.assert_called_once_with(user['name'], strict=True)
        self.lookup_name.assert_called_once_with('content_generator', cg['name'], strict=True)

    def test_with_create(self):
        self.ins_dup_check.return_value = True
        cg = {'id': 11, 'name': 'test-cg-name'}
        user = {'id': 123, 'name': 'testuser'}
        self.get_user.return_value = user
        self.lookup_name.return_value = cg
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.grant_cg_access(user['name'], cg['name'], create=True)
        self.assertEqual(f"User already has access to content generator {cg['name']}",
                         str(ex.exception))

        # check the insert
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'cg_users')
        self.assertEqual(insert.data, {'cg_id': cg['id'], 'user_id': user['id']})
        self.assertEqual(insert.rawdata, {})
        self.get_user.assert_called_once_with(user['name'], strict=True)
        self.lookup_name.assert_called_once_with('content_generator', cg['name'], create=True)
