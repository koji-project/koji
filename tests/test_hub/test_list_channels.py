import mock
import unittest

import koji
import kojihub

QP = kojihub.QueryProcessor


class TestListChannels(unittest.TestCase):
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


    def test_all(self):
        kojihub.list_channels()
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['channels'])
        self.assertEqual(query.aliases, ['id', 'name'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.values, {})
        self.assertEqual(query.columns, ['channels.id', 'channels.name'])
        self.assertEqual(query.clauses, None)

    def test_host(self):
        kojihub.list_channels(hostID=1234)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        joins = ['channels ON channels.id = host_channels.channel_id']
        clauses = [
            '(host_channels.active = TRUE)',
            'host_channels.host_id = %(host_id)s'
        ]
        self.assertEqual(query.tables, ['host_channels'])
        self.assertEqual(query.aliases, ['id', 'name'])
        self.assertEqual(query.joins, joins)
        self.assertEqual(query.values, {'host_id': 1234})
        self.assertEqual(query.columns, ['channels.id', 'channels.name'])
        self.assertEqual(query.clauses, clauses)

    def test_host_and_event(self):
        kojihub.list_channels(hostID=1234, event=2345)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        joins = ['channels ON channels.id = host_channels.channel_id']
        clauses = [
            '(host_channels.create_event <= 2345 AND ( host_channels.revoke_event IS NULL OR 2345 < host_channels.revoke_event ))',
            'host_channels.host_id = %(host_id)s',
        ]
        self.assertEqual(query.tables, ['host_channels'])
        self.assertEqual(query.aliases, ['id', 'name'])
        self.assertEqual(query.joins, joins)
        self.assertEqual(query.values, {'host_id': 1234})
        self.assertEqual(query.columns, ['channels.id', 'channels.name'])
        self.assertEqual(query.clauses, clauses)

    def test_event_only(self):
        with self.assertRaises(koji.GenericError):
            kojihub.list_channels(event=1234)
        self.assertEqual(len(self.queries), 0)
