import kojihub
import mock
import unittest

QP = kojihub.QueryProcessor


class TestGetReadyHosts(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_execute = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = self.query_execute
        self.queries.append(query)
        return query

    def test_valid(self):
        hosts = [{'host.id': 1, 'name': 'hostname', 'arches': 'arch123', 'task_load': 0,
                  'capacity': 3},
                 {'host.id': 2, 'name': 'hostname-2', 'arches': 'arch123', 'task_load': 0,
                  'capacity': 3}]
        expected_res = [{'host.id': 1, 'name': 'hostname', 'arches': 'arch123', 'task_load': 0,
                         'capacity': 3, 'channels': [1]},
                        {'host.id': 2, 'name': 'hostname-2', 'arches': 'arch123', 'task_load': 0,
                         'capacity': 3, 'channels': [2, 3]}
                        ]
        self.query_execute.side_effect = [hosts, [{'channel_id': 1}],
                                          [{'channel_id': 2}, {'channel_id': 3}]]
        result = kojihub.get_ready_hosts()
        self.assertEqual(result, expected_res)
        self.assertEqual(len(self.queries), 3)

        query = self.queries[0]
        self.assertEqual(query.tables, ['host'])
        self.assertEqual(query.joins, ['sessions USING (user_id)',
                                       'host_config ON host.id = host_config.host_id'])
        self.assertEqual(query.clauses, ['active IS TRUE', 'enabled IS TRUE', 'expired IS FALSE',
                                         'master IS NULL', 'ready IS TRUE',
                                         "update_time > NOW() - '5 minutes'::interval"])
        self.assertEqual(query.values, {})
        self.assertEqual(query.columns, ['arches', 'capacity', 'host.id', 'name', 'task_load'])

        query = self.queries[1]
        self.assertEqual(query.tables, ['host_channels'])
        self.assertEqual(query.joins, ['channels ON host_channels.channel_id = channels.id'])
        self.assertEqual(query.clauses, ['active IS TRUE', 'enabled IS TRUE', 'host_id=%(id)s'])
        self.assertEqual(query.values, hosts[0])
        self.assertEqual(query.columns, ['channel_id'])

        query = self.queries[2]
        self.assertEqual(query.tables, ['host_channels'])
        self.assertEqual(query.joins, ['channels ON host_channels.channel_id = channels.id'])
        self.assertEqual(query.clauses, ['active IS TRUE', 'enabled IS TRUE', 'host_id=%(id)s'])
        self.assertEqual(query.values, hosts[1])
        self.assertEqual(query.columns, ['channel_id'])
