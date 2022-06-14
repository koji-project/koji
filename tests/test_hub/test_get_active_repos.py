import mock
import unittest
import koji
import kojihub
import koji.db


QP = kojihub.QueryProcessor


class TestGetActiveRepos(unittest.TestCase):

    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        self.queries.append(query)
        return query

    def tearDown(self):
        mock.patch.stopall()

    def test_get_active_repos(self):
        # currently not really a lot of parameters to test
        result = kojihub.get_active_repos()
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        # make sure the following does not error
        str(query)
        self.assertEqual(query.tables, ['repo'])
        columns = ['repo.id', 'repo.state', 'repo.task_id', 'repo.create_event',
                   "date_part('epoch', events.time)", 'repo.tag_id', 'repo.dist', 'tag.name']
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(query.clauses, ['repo.state != %(st_deleted)s'])
        self.assertEqual(query.joins, ['tag ON repo.tag_id=tag.id',
                                       'events ON repo.create_event = events.id'])
        self.assertEqual(query.values['st_deleted'], koji.REPO_DELETED)
