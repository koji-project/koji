import mock

import kojihub
import kojihub.kojihub
from .utils import DBQueryTestCase


class TestUntaggedBuilds(DBQueryTestCase):
    def setUp(self):
        super(TestUntaggedBuilds, self).setUp()

    def tearDown(self):
        mock.patch.stopall()

    def test_valid_name_none(self):
        self.qp_iterate_return_value = [{'id': 1, 'name': 'pkg-name', 'version': '1',
                                         'release': '2'},
                                        {'id': 1, 'name': 'test-pkg', 'version': '2',
                                         'release': '3'}]
        expected_result = [{'id': 1, 'name': 'pkg-name', 'version': '1', 'release': '2'},
                           {'id': 1, 'name': 'test-pkg', 'version': '2', 'release': '3'}]
        rv = kojihub.untagged_builds()
        self.assertEqual(rv, expected_result)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['build', 'package'])
        self.assertEqual(query.columns,
                         ['build.id', 'package.name', 'build.release', 'build.version'])
        self.assertEqual(query.aliases, ['id', 'name', 'release', 'version'])
        self.assertEqual(query.clauses, ['NOT EXISTS\n'
                                         '             (SELECT 1 FROM tag_listing\n'
                                         '              WHERE tag_listing.build_id = build.id\n'
                                         '                AND tag_listing.active IS TRUE)',
                                         "build.state = %(st_complete)i",
                                         "package.id = build.pkg_id"])
        self.assertEqual(query.joins, None)

    def test_valid_with_name(self):
        self.qp_iterate_return_value = [{'id': 1, 'name': 'pkg-name', 'version': '1',
                                         'release': '2'}]
        expected_result = [{'id': 1, 'name': 'pkg-name', 'version': '1', 'release': '2'}]
        rv = kojihub.untagged_builds(name='pkg-name')
        self.assertEqual(rv, expected_result)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['build', 'package'])
        self.assertEqual(query.columns,
                         ['build.id', 'package.name', 'build.release', 'build.version'])
        self.assertEqual(query.aliases, ['id', 'name', 'release', 'version'])
        self.assertEqual(query.clauses, ['NOT EXISTS\n'
                                         '             (SELECT 1 FROM tag_listing\n'
                                         '              WHERE tag_listing.build_id = build.id\n'
                                         '                AND tag_listing.active IS TRUE)',
                                         "build.state = %(st_complete)i",
                                         "package.id = build.pkg_id",
                                         'package.name = %(name)s'])
        self.assertEqual(query.joins, None)
