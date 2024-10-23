from unittest import mock

import unittest
import datetime

from koji.context import context

import koji
import kojihub.repos


QP = kojihub.QueryProcessor
IP = kojihub.InsertProcessor
UP = kojihub.UpdateProcessor
RQ = kojihub.repos.RepoQuery


class TestRepoFunctions(unittest.TestCase):

    def setUp(self):
        self.RepoQuery = mock.patch('kojihub.repos.RepoQuery',
                                    side_effect=self.getQuery).start()
        self.queries = []
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self._dml = mock.patch('kojihub.kojihub._dml').start()
        self.exports = kojihub.RootExports()
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.get_tag_id = mock.patch('kojihub.kojihub.get_tag_id').start()
        self.query_executeOne = mock.MagicMock()
        self.context = mock.patch('kojihub.db.context').start()

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = RQ(*args, **kwargs)
        #query.execute = mock.MagicMock()
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

    def test_repo_expire_older(self):
        kojihub.repo_expire_older(mock.sentinel.tag_id, mock.sentinel.event_id)
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'repo')
        self.assertEqual(update.data, {'state': koji.REPO_EXPIRED})
        self.assertEqual(update.rawdata, {})
        self.assertEqual(update.values['event_id'], mock.sentinel.event_id)
        self.assertEqual(update.values['tag_id'], mock.sentinel.tag_id)
        self.assertEqual(update.values['dist'], None)
        if 'dist = %(dist)s' in update.clauses:
            raise Exception('Unexpected dist condition')

        # and with dist specified
        for dist in True, False:
            self.updates = []
            kojihub.repo_expire_older(mock.sentinel.tag_id, mock.sentinel.event_id,
                                      dist=dist)
            self.assertEqual(len(self.updates), 1)
            update = self.updates[0]
            self.assertEqual(update.table, 'repo')
            self.assertEqual(update.data, {'state': koji.REPO_EXPIRED})
            self.assertEqual(update.rawdata, {})
            self.assertEqual(update.values['event_id'], mock.sentinel.event_id)
            self.assertEqual(update.values['tag_id'], mock.sentinel.tag_id)
            self.assertEqual(update.values['dist'], dist)
            if 'dist = %(dist)s' not in update.clauses:
                raise Exception('Missing dist condition')

    def test_repo_info(self):
        rv = kojihub.repo_info(3)
        self.RepoQuery.assert_called_once()

    def test_get_repo_default(self):
        self.get_tag_id.return_value = 100

        self.exports.getRepo('TAG')

        self.RepoQuery.assert_called_once()
        qv = self.queries[0]
        self.assertEqual(len(self.queries), 1)
        self.assertEqual(qv.clauses,
                         [['tag_id', '=', 100], ['dist', 'IS', False], ['state', '=', 1]])

    def test_get_repo_with_dist_and_event(self):
        self.get_tag_id.return_value = 100

        self.exports.getRepo('TAG', event=111, dist=True)

        self.RepoQuery.assert_called_once()
        qv = self.queries[0]
        self.assertEqual(len(self.queries), 1)
        self.assertEqual(qv.clauses,
                         [['tag_id', '=', 100],
                          ['dist', 'IS', True],
                          ['create_event', '<=', 111]])

    def test_get_repo_with_min_event(self):
        self.get_tag_id.return_value = 100

        self.exports.getRepo('TAG', min_event=101010)

        self.RepoQuery.assert_called_once()
        qv = self.queries[0]
        self.assertEqual(len(self.queries), 1)
        self.assertEqual(qv.clauses,
                         [['tag_id', '=', 100],
                          ['dist', 'IS', False],
                          ['state', '=', 1],
                          ['create_event', '>=', 101010]])


# the end
