import unittest
import mock
import kojihub

QP = kojihub.QueryProcessor


class TestQueryBuildroots(unittest.TestCase):

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = self.query_execute
        self.queries.append(query)
        return query

    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.repo_references = mock.patch('kojihub.kojihub.repo_references').start()
        self.queries = []
        self.query_execute = mock.MagicMock()

    def test_query_buildroots(self):
        self.query_execute.side_effect = [[7], [7], [7], []]
        self.repo_references.return_value = [{'id': 7, 'host_id': 1, 'create_event': 333,
                                             'state': 1}]
        kojihub.query_buildroots(hostID=1, tagID=2, state=1, rpmID=3, archiveID=4, taskID=5,
                                 buildrootID=7, repoID=10)
        self.assertEqual(len(self.queries), 4)
        query = self.queries[0]
        self.assertEqual(query.tables, ['buildroot_listing'])
        self.assertEqual(query.columns, ['buildroot_id'])
        self.assertEqual(query.clauses, ['rpm_id = %(rpmID)i'])
        self.assertEqual(query.joins, None)
        query = self.queries[1]
        self.assertEqual(query.tables, ['buildroot_archives'])
        self.assertEqual(query.columns, ['buildroot_id'])
        self.assertEqual(query.clauses, ['archive_id = %(archiveID)i'])
        self.assertEqual(query.joins, None)
        query = self.queries[2]
        self.assertEqual(query.tables, ['standard_buildroot'])
        self.assertEqual(query.columns, ['buildroot_id'])
        self.assertEqual(query.clauses, ['task_id = %(taskID)i'])
        self.assertEqual(query.joins, None)
        query = self.queries[3]
        self.assertEqual(query.tables, ['standard_buildroot'])
        self.assertEqual(query.columns, ['buildroot_id'])
        self.assertEqual(query.clauses, ['repo_id = %(repoID)i'])
        self.assertEqual(query.joins, None)

    def test_query_buildroots_some_params_as_list(self):
        kojihub.query_buildroots(state=[1], buildrootID=[7])
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['buildroot'])
        self.assertEqual(query.clauses, ['buildroot.id IN %(buildrootID)s',
                                         'standard_buildroot.state IN %(state)s'])
        self.assertEqual(query.joins,
                         ['LEFT OUTER JOIN standard_buildroot ON '
                          'standard_buildroot.buildroot_id = buildroot.id',
                          'LEFT OUTER JOIN content_generator ON '
                          'buildroot.cg_id = content_generator.id',
                          'LEFT OUTER JOIN host ON host.id = standard_buildroot.host_id',
                          'LEFT OUTER JOIN repo ON repo.id = standard_buildroot.repo_id',
                          'LEFT OUTER JOIN tag ON tag.id = repo.tag_id',
                          'LEFT OUTER JOIN events AS create_events ON '
                          'create_events.id = standard_buildroot.create_event',
                          'LEFT OUTER JOIN events AS retire_events ON '
                          'standard_buildroot.retire_event = retire_events.id',
                          'LEFT OUTER JOIN events AS repo_create ON '
                          'repo_create.id = repo.create_event'])
