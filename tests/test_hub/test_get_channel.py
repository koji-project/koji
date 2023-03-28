import mock

import koji
import kojihub
from .utils import DBQueryTestCase


class TestGetChannel(DBQueryTestCase):

    def setUp(self):
        super(TestGetChannel, self).setUp()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.exports = kojihub.RootExports()

    def test_wrong_type_channelInfo(self):
        # dict
        channel_info = {'channel': 'val'}
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getChannel(channel_info)
        self.assertEqual('Invalid name or id value: %s' % channel_info,
                         str(cm.exception))

        # list
        channel_info = ['channel']
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getChannel(channel_info)
        self.assertEqual('Invalid name or id value: %s' % channel_info,
                         str(cm.exception))

    def test_query_by_name(self):
        self.exports.getChannel('my_channel')
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        clauses = ['(channels.name = %(channels_name)s)']
        values = {'channels_name': 'my_channel'}
        self.assertEqual(query.tables, ['channels'])
        self.assertEqual(query.joins, None)
        self.assertEqual(set(query.clauses), set(clauses))
        self.assertEqual(query.values, values)

    def test_query_by_id(self):
        self.exports.getChannel(12345)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        clauses = ['(channels.id = %(channels_id)s)']
        values = {'channels_id': 12345}
        self.assertEqual(query.tables, ['channels'])
        self.assertEqual(query.joins, None)
        self.assertEqual(set(query.clauses), set(clauses))
        self.assertEqual(query.values, values)

    def test_query_by_dict(self):
        self.exports.getChannel({'id': 12345, 'name': 'whatever'})
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        clauses = ['(channels.id = %(channels_id)s)']
        values = {'channels_id': 12345}
        self.assertEqual(query.tables, ['channels'])
        self.assertEqual(query.joins, None)
        self.assertEqual(set(query.clauses), set(clauses))
        self.assertEqual(query.values, values)
