import mock
import unittest

import koji
import kojihub

QP = kojihub.QueryProcessor


class TestSetHostEnabled(unittest.TestCase):
    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = mock.MagicMock()
        self.queries.append(query)
        return query

    def setUp(self):
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                                          side_effect=self.getQuery).start()
        self.queries = []
        self.context = mock.patch('kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.exports = kojihub.RootExports()

    def tearDown(self):
        mock.patch.stopall()

    def test_get_host_by_name(self):
        self.exports.getHost('hostname')

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        columns = ['host.id', 'host.user_id', 'host.name', 'host.ready',
                'host.task_load', 'host_config.arches',
                'host_config.capacity', 'host_config.description',
                'host_config.comment', 'host_config.enabled']
        joins = ['host ON host.id = host_config.host_id']
        aliases = ['id', 'user_id', 'name', 'ready', 'task_load',
                'arches', 'capacity', 'description', 'comment', 'enabled']
        clauses = ['(host_config.active = TRUE)', 'host.name = %(hostInfo)s']
        values = {'hostInfo': 'hostname'}
        self.assertEqual(query.tables, ['host_config'])
        self.assertEqual(query.joins, joins)
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(set(query.aliases), set(aliases))
        self.assertEqual(query.clauses, clauses)
        self.assertEqual(query.values, values)

    def test_get_host_by_id_event(self):
        self.exports.getHost(123, event=345)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        columns = ['host.id', 'host.user_id', 'host.name', 'host.ready',
                'host.task_load', 'host_config.arches',
                'host_config.capacity', 'host_config.description',
                'host_config.comment', 'host_config.enabled']
        joins = ['host ON host.id = host_config.host_id']
        aliases = ['id', 'user_id', 'name', 'ready', 'task_load',
                'arches', 'capacity', 'description', 'comment', 'enabled']
        clauses = ['(host_config.create_event <= 345 AND ( host_config.revoke_event IS NULL OR 345 < host_config.revoke_event ))',
                'host.id = %(hostInfo)i']
        values = {'hostInfo': 123}
        self.assertEqual(query.tables, ['host_config'])
        self.assertEqual(query.joins, joins)
        self.assertEqual(set(query.columns), set(columns))
        self.assertEqual(set(query.aliases), set(aliases))
        self.assertEqual(query.clauses, clauses)
        self.assertEqual(query.values, values)

    def getQueryMissing(self, *args, **kwargs):
        q = self.getQuery(*args, **kwargs)
        q.executeOne.return_value = []
        return q

    def test_get_host_missing(self):
        self.QueryProcessor.side_effect = self.getQueryMissing

        r = self.exports.getHost(123)
        self.assertEqual(r, None)

        with self.assertRaises(koji.GenericError):
            self.exports.getHost(123, strict=True)

        self.assertEqual(len(self.queries), 2)

        self.QueryProcessor.side_effect = self.getQuery

    def test_get_host_invalid_hostinfo(self):
        with self.assertRaises(koji.GenericError):
            self.exports.getHost({'host_id': 567})

        self.assertEqual(len(self.queries), 0)
