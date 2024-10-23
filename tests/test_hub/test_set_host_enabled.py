from unittest import mock
import unittest

import koji
import kojihub

UP = kojihub.UpdateProcessor
IP = kojihub.InsertProcessor


class TestSetHostEnabled(unittest.TestCase):
    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context_db = mock.patch('kojihub.db.context').start()
        self.get_host = mock.patch('kojihub.kojihub.get_host').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context_db.session.assertLogin = mock.MagicMock()
        self.context.session.assertPerm = mock.MagicMock()
        self.exports = kojihub.RootExports()

    def tearDown(self):
        mock.patch.stopall()

    def test_enableHost_missing(self):
        # non-existing hostname
        self.get_host.return_value = {}
        with self.assertRaises(koji.GenericError):
            self.exports.enableHost('hostname')
        self.assertEqual(self.updates, [])
        self.assertEqual(self.inserts, [])
        self.get_host.assert_called_once_with('hostname')

    def test_enableHost_valid(self):
        hostinfo = {
            'id': 123,
            'user_id': 234,
            'name': 'hostname',
            'arches': ['x86_64'],
            'capacity': 100.0,
            'description': 'description',
            'comment': 'comment',
            'enabled': False,
        }
        self.get_host.return_value = hostinfo
        self.context_db.event_id = 42
        self.context_db.session.user_id = 23

        self.exports.enableHost('hostname')

        self.get_host.assert_called_once_with('hostname')
        # revoke
        self.assertEqual(len(self.updates), 1)
        values = self.get_host.return_value
        clauses = ['host_id = %(id)i', 'active = TRUE']
        revoke_data = {
            'revoke_event': 42,
            'revoker_id': 23
        }
        revoke_rawdata = {'active': 'NULL'}
        update = self.updates[0]
        self.assertEqual(update.table, 'host_config')
        self.assertEqual(update.values, values)
        self.assertEqual(update.clauses, clauses)
        self.assertEqual(update.data, revoke_data)
        self.assertEqual(update.rawdata, revoke_rawdata)

        # insert
        insert = self.inserts[0]
        data = hostinfo
        data['create_event'] = 42
        data['creator_id'] = 23
        data['enabled'] = True
        data['host_id'] = data['id']
        del data['id']
        del data['name']
        del data['user_id']
        rawdata = {}
        self.assertEqual(insert.table, 'host_config')
        self.assertEqual(insert.data, data)
        self.assertEqual(insert.rawdata, rawdata)

        self.assertEqual(len(self.inserts), 1)

    def test_disableHost_valid(self):
        hostinfo = {
            'id': 123,
            'user_id': 234,
            'name': 'hostname',
            'arches': ['x86_64'],
            'capacity': 100.0,
            'description': 'description',
            'comment': 'comment',
            'enabled': True,
        }
        self.get_host.return_value = hostinfo
        self.context_db.event_id = 42
        self.context_db.session.user_id = 23

        self.exports.disableHost('hostname')

        self.get_host.assert_called_once_with('hostname')
        # revoke
        self.assertEqual(len(self.updates), 1)
        values = self.get_host.return_value
        clauses = ['host_id = %(id)i', 'active = TRUE']
        revoke_data = {
            'revoke_event': 42,
            'revoker_id': 23
        }
        revoke_rawdata = {'active': 'NULL'}
        update = self.updates[0]
        self.assertEqual(update.table, 'host_config')
        self.assertEqual(update.values, values)
        self.assertEqual(update.clauses, clauses)
        self.assertEqual(update.data, revoke_data)
        self.assertEqual(update.rawdata, revoke_rawdata)

        # insert
        insert = self.inserts[0]
        data = hostinfo
        data['create_event'] = 42
        data['creator_id'] = 23
        data['enabled'] = False
        data['host_id'] = data['id']
        del data['id']
        del data['name']
        del data['user_id']
        rawdata = {}
        self.assertEqual(insert.table, 'host_config')
        self.assertEqual(insert.data, data)
        self.assertEqual(insert.rawdata, rawdata)

        self.assertEqual(len(self.inserts), 1)
