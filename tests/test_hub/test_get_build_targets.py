import unittest

import mock

import kojihub

QP = kojihub.QueryProcessor


class TestGetBuildTargets(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.name_or_id_clause = mock.patch('kojihub.name_or_id_clause').start()
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.context').start()
        self.cursor = mock.MagicMock()
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.build_target = 'build-target'
        self.build_tag = 'tag'
        self.dest_tag = 'dest-tag'

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = mock.MagicMock()
        self.queries.append(query)
        return query

    def test_get_build_targets(self):
        self.name_or_id_clause.return_value = '(build_target.name = %(build_target_name)s)', \
                                              {'build_target_name': 'build-target-url'}
        kojihub.get_build_targets(self.build_target, buildTagID=self.build_tag,
                                  destTagID=self.dest_tag)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['build_target_config'])
        self.assertEqual(query.joins,
                         ['build_target ON build_target_config.build_target_id = build_target.id',
                          'tag AS tag1 ON build_target_config.build_tag = tag1.id',
                          'tag AS tag2 ON build_target_config.dest_tag = tag2.id'])
        self.assertEqual(query.clauses,
                         ['(active = TRUE)', '(build_target.name = %(build_target_name)s)',
                          'build_tag = %(buildTagID)i', 'dest_tag = %(destTagID)i'])
