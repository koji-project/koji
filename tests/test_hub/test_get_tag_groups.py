from unittest import mock
import unittest

import kojihub

QP = kojihub.QueryProcessor


class TestGetTagGroups(unittest.TestCase):
    def setUp(self):
        self.exports = kojihub.RootExports()
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_execute = mock.MagicMock()
        self.maxDiff = None
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context_db = mock.patch('kojihub.db.context').start()
        self.get_tag_id = mock.patch('kojihub.kojihub.get_tag_id').start()
        self.read_full_inheritance = mock.patch('kojihub.kojihub.readFullInheritance').start()

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = self.query_execute
        query.executeOne = mock.MagicMock()
        query.singleValue = mock.MagicMock()
        self.queries.append(query)
        return query

    def tearDown(self):
        mock.patch.stopall()

    def test_valid(self):
        tag_name = 'test-tag'
        self.get_tag_id.return_value = 11
        self.read_full_inheritance.return_value = [
            {
                'child_id': 123,
                'currdepth': 1,
                'filter': [],
                'intransitive': False,
                'maxdepth': None,
                'name': tag_name,
                'nextdepth': None,
                'noconfig': False,
                'parent_id': 1234,
                'pkg_filter': '',
                'priority': 0
            }
        ]
        self.query_execute.side_effect = [
            [{'group_id': 1, 'blocked': True}], [{'group_id': 2, 'blocked': False}],
            [{'group_id': 1, 'package': 'pkg'}], [{'group_id': 2, 'package': 'pkg-2'}],
            [{'group_id': 1, 'req_id': 1}], [{'group_id': 2, 'req_id': 2}]]
        kojihub.get_tag_groups(tag_name)

        self.assertEqual(len(self.queries), 6)
        clauses = ['(active = TRUE)', 'tag_id = %(tagid)s']
        values = {'tagid': 11}

        for i in range(0, 1):
            query = self.queries[i]
            columns = ['biarchonly', 'blocked', 'description', 'display_name', 'exported',
                       'group_id', 'is_default', 'langonly', 'name', 'tag_id', 'uservisible']
            self.assertEqual(query.tables, ['group_config'])
            self.assertEqual(query.joins, ['groups ON group_id = id'])
            self.assertEqual(query.values, values)
            self.assertEqual(query.columns, columns)
            self.assertEqual(query.clauses, clauses)

        for i in range(2, 3):
            query = self.queries[i]
            columns = \
                ['basearchonly', 'blocked', 'group_id', 'package', 'requires', 'tag_id', 'type']
            self.assertEqual(query.tables, ['group_package_listing'])
            self.assertEqual(query.joins, None)
            self.assertEqual(query.values, values)
            self.assertEqual(query.columns, columns)
            self.assertEqual(query.clauses, clauses)

        for i in range(4, 5):
            query = self.queries[i]
            columns = ['blocked', 'group_id', 'is_metapkg', 'name', 'req_id', 'tag_id', 'type']
            self.assertEqual(query.tables, ['group_req_listing'])
            self.assertEqual(query.joins, ['groups on req_id = id'])
            self.assertEqual(query.values, values)
            self.assertEqual(query.columns, columns)
            self.assertEqual(query.clauses, clauses)

    def test_valid_group_not_in_groups(self):
        tag_name = 'test-tag'
        self.get_tag_id.return_value = 11
        self.read_full_inheritance.return_value = [
            {
                'child_id': 123,
                'currdepth': 1,
                'filter': [],
                'intransitive': False,
                'maxdepth': None,
                'name': tag_name,
                'nextdepth': None,
                'noconfig': False,
                'parent_id': 1234,
                'pkg_filter': '',
                'priority': 0
            }
        ]
        self.query_execute.side_effect = [
            [{'group_id': 1, 'blocked': True}], [{'group_id': 2, 'blocked': False}],
            [{'group_id': 2, 'package': 'pkg'}], [{'group_id': 3, 'package': 'pkg-2'}],
            [{'group_id': 4, 'req_id': 6}], [{'group_id': 2, 'req_id': 7}]]
        kojihub.get_tag_groups(tag_name)

        self.assertEqual(len(self.queries), 6)
        clauses = ['(active = TRUE)', 'tag_id = %(tagid)s']
        values = {'tagid': 11}

        for i in range(0, 1):
            query = self.queries[i]
            columns = ['biarchonly', 'blocked', 'description', 'display_name', 'exported',
                       'group_id', 'is_default', 'langonly', 'name', 'tag_id', 'uservisible']
            self.assertEqual(query.tables, ['group_config'])
            self.assertEqual(query.joins, ['groups ON group_id = id'])
            self.assertEqual(query.values, values)
            self.assertEqual(query.columns, columns)
            self.assertEqual(query.clauses, clauses)

        for i in range(2, 3):
            query = self.queries[i]
            columns = \
                ['basearchonly', 'blocked', 'group_id', 'package', 'requires', 'tag_id', 'type']
            self.assertEqual(query.tables, ['group_package_listing'])
            self.assertEqual(query.joins, None)
            self.assertEqual(query.values, values)
            self.assertEqual(query.columns, columns)
            self.assertEqual(query.clauses, clauses)

        for i in range(4, 5):
            query = self.queries[i]
            columns = ['blocked', 'group_id', 'is_metapkg', 'name', 'req_id', 'tag_id', 'type']
            self.assertEqual(query.tables, ['group_req_listing'])
            self.assertEqual(query.joins, ['groups on req_id = id'])
            self.assertEqual(query.values, values)
            self.assertEqual(query.columns, columns)
            self.assertEqual(query.clauses, clauses)
