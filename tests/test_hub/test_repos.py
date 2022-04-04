import mock

import unittest
import datetime

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
        self.exports = kojihub.RootExports()
        self.get_tag = mock.patch('kojihub.get_tag').start()

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

    @mock.patch('kojihub._singleRow')
    def test_repo_info(self, _singleRow):
        repo_row = {'id': 10,
                    'state': 0,
                    'task_id': 15,
                    'create_event': 32,
                    'creation_time': datetime.datetime(2021, 3, 30, 12, 34, 5, 204023,
                                                       tzinfo=datetime.timezone.utc),
                    'create_ts': 1617107645.204023,
                    'tag_id': 3,
                    'tag_name': 'test-tag',
                    'dist': False}
        _singleRow.return_value = repo_row
        rv = kojihub.repo_info(3)
        self.assertEqual(rv, repo_row)

    def test_get_repo_default(self):
        self.exports.getRepo(2)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        # make sure the following does not error
        str(query)
        self.assertEqual(query.tables, ['repo'])
        columns = ['repo.id', 'repo.state', 'repo.task_id', 'repo.create_event',
                   'EXTRACT(EPOCH FROM events.time)', 'repo.dist', 'events.time']
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(query.joins, ['events ON repo.create_event = events.id'])
        self.assertEqual(query.clauses, ['repo.dist is false', 'repo.state = %(state)s',
                                         'repo.tag_id = %(id)i'])

    def test_get_repo_with_dist_and_event(self):
        self.exports.getRepo(2, event=111, dist=True)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        # make sure the following does not error
        str(query)
        self.assertEqual(query.tables, ['repo'])
        columns = ['repo.id', 'repo.state', 'repo.task_id', 'repo.create_event',
                   'EXTRACT(EPOCH FROM events.time)', 'repo.dist', 'events.time']
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(query.joins, ['events ON repo.create_event = events.id'])
        self.assertEqual(query.clauses, ['create_event <= %(event)i', 'repo.dist is true',
                                         'repo.tag_id = %(id)i'])
