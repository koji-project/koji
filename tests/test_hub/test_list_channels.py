import unittest

from unittest import mock

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
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.exports = kojihub.RootExports()
        self.get_host = mock.patch('kojihub.kojihub.get_host').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_all(self):
        kojihub.list_channels()
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['channels'])
        self.assertEqual(query.aliases, ['comment', 'description', 'enabled', 'id',
                                         'name'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.values, {})
        self.assertEqual(query.columns, ['channels.comment', 'channels.description',
                                         'channels.enabled', 'channels.id', 'channels.name'])
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
        self.assertEqual(query.aliases, ['comment', 'description', 'enabled', 'id',
                                         'name'])
        self.assertEqual(query.joins, joins)
        self.assertEqual(query.values, {'host_id': 1234})
        self.assertEqual(query.columns, ['channels.comment', 'channels.description',
                                         'channels.enabled', 'channels.id', 'channels.name'])
        self.assertEqual(query.clauses, clauses)

    def test_host_and_event(self):
        kojihub.list_channels(hostID=1234, event=2345)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        joins = ['channels ON channels.id = host_channels.channel_id']
        clauses = [
            '(host_channels.create_event <= 2345 AND ( host_channels.revoke_event '
            'IS NULL OR 2345 < host_channels.revoke_event ))',
            'host_channels.host_id = %(host_id)s',
        ]
        self.assertEqual(query.tables, ['host_channels'])
        self.assertEqual(query.aliases, ['comment', 'description', 'enabled', 'id',
                                         'name'])
        self.assertEqual(query.joins, joins)
        self.assertEqual(query.values, {'host_id': 1234})
        self.assertEqual(query.columns, ['channels.comment', 'channels.description',
                                         'channels.enabled', 'channels.id', 'channels.name'])
        self.assertEqual(query.clauses, clauses)

    def test_event_only(self):
        with self.assertRaises(koji.GenericError):
            kojihub.list_channels(event=1234)
        self.assertEqual(len(self.queries), 0)

    def test_enabled_is_true_host_string(self):
        self.get_host.return_value = {'arches': 'x86_64', 'capacity': 2.0, 'comment': None,
                                      'description': None, 'enabled': True, 'id': 1234,
                                      'name': 'test-host', 'ready': False, 'task_load': 0.0,
                                      'user_id': 2}
        kojihub.list_channels(hostID='test-host', enabled=True)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        joins = ['channels ON channels.id = host_channels.channel_id']
        clauses = [
            '(host_channels.active = TRUE)',
            'enabled IS TRUE',
            'host_channels.host_id = %(host_id)s'
        ]
        self.assertEqual(query.tables, ['host_channels'])
        self.assertEqual(query.aliases, ['comment', 'description', 'enabled', 'id', 'name'])
        self.assertEqual(query.joins, joins)
        self.assertEqual(query.values, {'host_id': 1234})
        self.assertEqual(query.columns, ['channels.comment', 'channels.description',
                                         'channels.enabled', 'channels.id', 'channels.name'])
        self.assertEqual(query.clauses, clauses)

    def test_enabled_is_false(self):
        kojihub.list_channels(enabled=False)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        clauses = [
            'enabled IS FALSE',
        ]
        self.assertEqual(query.tables, ['channels'])
        self.assertEqual(query.aliases, ['comment', 'description', 'enabled', 'id', 'name'])
        self.assertEqual(query.columns, ['channels.comment', 'channels.description',
                                         'channels.enabled', 'channels.id', 'channels.name'])
        self.assertEqual(query.clauses, clauses)
