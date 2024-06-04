import mock

import kojihub
from .utils import DBQueryTestCase


class TestGetBuildTargets(DBQueryTestCase):

    def setUp(self):
        super(TestGetBuildTargets, self).setUp()
        self.maxDiff = None
        self.name_or_id_clause = mock.patch('kojihub.kojihub.name_or_id_clause').start()
        self.get_tag_id = mock.patch('kojihub.kojihub.get_tag_id').start()
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.cursor = mock.MagicMock()
        self.build_target = 'build-target'
        self.build_tag_name = 'tag'
        self.dest_tag_name = 'dest-tag'
        self.build_tag_id = 1
        self.dest_tag_id = 2

    def tearDown(self):
        mock.patch.stopall()

    def test_get_build_targets_strings(self):
        self.name_or_id_clause.return_value = '(build_target.name = %(build_target_name)s)', \
                                              {'build_target_name': 'build-target-url'}
        self.get_tag_id.side_effect = [[self.build_tag_id], [self.dest_tag_id]]
        kojihub.get_build_targets(self.build_target, buildTagID=self.build_tag_name,
                                  destTagID=self.dest_tag_name)
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

    def test_get_build_targets_integers(self):
        self.name_or_id_clause.return_value = '(build_target.name = %(build_target_name)s)', \
                                              {'build_target_name': 'build-target-url'}
        kojihub.get_build_targets(self.build_target, buildTagID=self.build_tag_id,
                                  destTagID=self.dest_tag_id)
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
