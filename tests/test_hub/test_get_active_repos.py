from unittest import mock
import unittest
import koji
import kojihub.repos

from koji.context import context


RQ = kojihub.repos.RepoQuery


class TestGetActiveRepos(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.db.context').start()
        self.RepoQuery = mock.patch('kojihub.kojihub.repos.RepoQuery',
                                    side_effect=self.getQuery).start()
        self.queries = []

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = RQ(*args, **kwargs)
        #query.execute = mock.MagicMock()
        self.queries.append(query)
        return query

    def test_get_active_repos(self):
        kojihub.get_active_repos()
        self.RepoQuery.assert_called_once()
        query = self.queries[0]
        self.assertEqual(len(query.clauses), 1)
