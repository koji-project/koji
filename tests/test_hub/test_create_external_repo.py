# coding: utf-8
import unittest

import mock

import koji
import kojihub

IP = kojihub.InsertProcessor


class TestCreateExternalRepo(unittest.TestCase):

    def setUp(self):
        self.get_external_repos = mock.patch('kojihub.kojihub.get_external_repos').start()
        self.verify_name_internal = mock.patch('kojihub.kojihub.verify_name_internal').start()
        self.get_external_repo_id = mock.patch('kojihub.kojihub.get_external_repo_id').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()
        self.repo_url = 'http://path_to_ext_repo.com'
        self.repo_name = 'test-repo'
        self.repo_info = {'id': 1, 'name': self.repo_name, 'url': self.repo_url}
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.context_db = mock.patch('kojihub.db.context').start()
        self.context_db.session.assertLogin = mock.MagicMock()

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def tearDown(self):
        mock.patch.stopall()

    def test_create_external_repo_wrong_format(self):
        repo_name = 'test-repo+'

        # name is longer as expected
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.create_external_repo(repo_name, self.repo_url)

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.create_external_repo(repo_name, self.repo_url)

    def test_create_external_repo_exists(self):
        expected = 'An external repo named "%s" already exists' % self.repo_name

        self.verify_name_internal.return_value = None
        self.get_external_repos.return_value = self.repo_info
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.create_external_repo(self.repo_name, self.repo_url)
        self.assertEqual(expected, str(cm.exception))

    def test_valid(self):
        self.verify_name_internal.return_value = None
        self.get_external_repos.return_value = None
        self.context_db.event_id = 42
        self.context_db.session.user_id = 23
        self.get_external_repo_id.return_value = self.repo_info['id']
        repo_url = self.repo_url + '/'
        result = kojihub.create_external_repo(self.repo_name, self.repo_url)
        self.assertEqual(result,
                         {'id': self.repo_info['id'], 'name': self.repo_name, 'url': repo_url})
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'external_repo_config')
        self.assertEqual(insert.data, {
            'create_event': 42,
            'creator_id': 23,
            'external_repo_id': self.repo_info['id'],
            'url': repo_url
        })
        self.assertEqual(insert.rawdata, {})
