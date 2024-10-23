# coding: utf-8
import unittest

from unittest import mock

import koji
import kojihub

IP = kojihub.InsertProcessor
QP = kojihub.QueryProcessor
UP = kojihub.UpdateProcessor


class TestEditExternalRepo(unittest.TestCase):

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = mock.MagicMock()
        query.singleValue = self.query_singleValue
        self.queries.append(query)
        return query

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.get_external_repo = mock.patch('kojihub.kojihub.get_external_repo').start()
        self.verify_name_internal = mock.patch('kojihub.kojihub.verify_name_internal').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()
        self.repo_url = 'http://path_to_ext_repo.com'
        self.repo_name = 'test-repo'
        self.repo_info = {'id': 1, 'name': self.repo_name, 'url': self.repo_url}
        self.context_db = mock.patch('kojihub.db.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context_db.session.assertLogin = mock.MagicMock()
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_singleValue = mock.MagicMock()
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []

    def tearDown(self):
        mock.patch.stopall()

    def test_edit_external_repo_wrong_format(self):
        repo_name_new = 'test-repo+'
        self.get_external_repo.return_value = self.repo_info

        # name is longer as expected
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.edit_external_repo(self.repo_name, repo_name_new, self.repo_url)

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.edit_external_repo(self.repo_name, repo_name_new, self.repo_url)

    def test_edit_external_repo_existing_name(self):
        repo_name_new = 'test-repo+'
        self.get_external_repo.return_value = self.repo_info
        self.verify_name_internal.side_effect = None
        self.query_singleValue.return_value = 111
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.edit_external_repo(self.repo_name, repo_name_new, self.repo_url)
        self.assertEqual(f'name "{repo_name_new}" is already taken by external repo {111}',
                         str(ex.exception))
        self.assertEqual(len(self.queries), 1)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

        query = self.queries[0]
        self.assertEqual(query.tables, ['external_repo'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['name = %(name)s'])
        self.assertEqual(query.columns, ['id'])
        self.assertEqual(query.values, {'name': repo_name_new})

    def test_edit_valid(self):
        path_to_new_repo = 'http://path_to_new_ext_repo.com'
        repo_name_new = 'test-repo+'
        self.get_external_repo.return_value = self.repo_info
        self.verify_name_internal.side_effect = None
        self.query_singleValue.return_value = None
        self.context_db.event_id = 42
        self.context_db.session.user_id = 23
        kojihub.edit_external_repo(self.repo_name, repo_name_new, path_to_new_repo)

        self.assertEqual(len(self.queries), 1)
        self.assertEqual(len(self.inserts), 1)
        self.assertEqual(len(self.updates), 2)

        query = self.queries[0]
        self.assertEqual(query.tables, ['external_repo'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['name = %(name)s'])
        self.assertEqual(query.columns, ['id'])
        self.assertEqual(query.values, {'name': repo_name_new})

        insert = self.inserts[0]
        self.assertEqual(insert.table, 'external_repo_config')
        self.assertEqual(insert.data, {
            'create_event': 42,
            'creator_id': 23,
            'external_repo_id': self.repo_info['id'],
            'url': path_to_new_repo + '/'
        })
        self.assertEqual(insert.rawdata, {})

        update = self.updates[0]
        self.assertEqual(update.table, 'external_repo')
        self.assertEqual(update.values, {'repo_id': self.repo_info['id']})
        self.assertEqual(update.clauses, ['id = %(repo_id)i'])
        self.assertEqual(update.data, {'name': repo_name_new})
        self.assertEqual(update.rawdata, {})

        update = self.updates[1]
        self.assertEqual(update.table, 'external_repo_config')
        self.assertEqual(update.clauses, ['external_repo_id = %(repo_id)i', 'active = TRUE'])
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 23})
        self.assertEqual(update.rawdata, {'active': 'NULL'})
