import mock

import unittest

import koji
import kojihub


QP = kojihub.QueryProcessor
IP = kojihub.InsertProcessor
UP = kojihub.UpdateProcessor


class TestRepoFunctions(unittest.TestCase):

    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                side_effect=self.getQuery).start()
        self.queries = []
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.UpdateProcessor',
                side_effect=self.getUpdate).start()
        self.updates = []
        self._dml = mock.patch('kojihub._dml').start()

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
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
