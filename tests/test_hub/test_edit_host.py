import mock
import unittest

import koji
import kojihub

UP = kojihub.UpdateProcessor
IP = kojihub.InsertProcessor


class TestEditHost(unittest.TestCase):
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
        self.diff = None
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.context = mock.patch('kojihub.context').start()
        self.context_db = mock.patch('koji.db.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context_db.session.assertLogin = mock.MagicMock()
        self.context.session.assertPerm = mock.MagicMock()
        self.exports = kojihub.RootExports()
        self.get_host = mock.patch('kojihub.get_host').start()
        self.hostinfo = {
            'id': 123,
            'user_id': 234,
            'name': 'hostname',
            'arches': 'x86_64',
            'capacity': 100.0,
            'description': 'description',
            'comment': 'comment',
            'enabled': False,
        }

    def tearDown(self):
        mock.patch.stopall()

    def test_edit_host_missing(self):
        kojihub.get_host.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.editHost('hostname')
        kojihub.get_host.assert_called_once_with('hostname', strict=True)
        self.assertEqual(self.inserts, [])
        self.assertEqual(self.updates, [])

    def test_edit_host_invalid_description(self):
        description = ['description']
        kojihub.get_host.return_value = self.hostinfo
        with self.assertRaises(koji.ParameterError) as ex:
            self.exports.editHost('hostname', description=description)
            self.assertEqual('Invalid type for description parameter: %s' % type(description),
                             str(ex.exception))
        kojihub.get_host.assert_called_once_with('hostname', strict=True)
        self.assertEqual(self.inserts, [])
        self.assertEqual(self.updates, [])

    def test_edit_host_invalid_comment_parameter(self):
        comment = ['comment']
        kojihub.get_host.return_value = self.hostinfo
        with self.assertRaises(koji.ParameterError) as ex:
            self.exports.editHost('hostname', comment=comment)
            self.assertEqual('Invalid type for comment parameter: %s' % type(comment),
                             str(ex.exception))
        kojihub.get_host.assert_called_once_with('hostname', strict=True)
        self.assertEqual(self.inserts, [])
        self.assertEqual(self.updates, [])

    def test_edit_host_invalid_arches_parameter(self):
        arches = ['arches arches']
        kojihub.get_host.return_value = self.hostinfo
        with self.assertRaises(koji.ParameterError) as ex:
            self.exports.editHost('hostname', arches=arches)
            self.assertEqual('Invalid type for arches parameter: %s' % type(arches),
                             str(ex.exception))
        kojihub.get_host.assert_called_once_with('hostname', strict=True)
        self.assertEqual(self.inserts, [])
        self.assertEqual(self.updates, [])

    def test_edit_host_valid(self):
        kojihub.get_host = mock.MagicMock()
        kojihub.get_host.return_value = self.hostinfo
        self.context_db.event_id = 42
        self.context_db.session.user_id = 23

        r = self.exports.editHost('hostname', arches='x86_64 i386', capacity=12.0,
                                  comment='comment_new', non_existing_kw='bogus')

        self.assertTrue(r)
        kojihub.get_host.assert_called_once_with('hostname', strict=True)

        # revoke
        self.assertEqual(len(self.updates), 1)
        values = kojihub.get_host.return_value
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
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        data = {
            'create_event': 42,
            'creator_id': 23,
            'host_id': 123,
            'arches': 'x86_64 i386',
            'capacity': 12.0,
            'comment': 'comment_new',
            'description': 'description',
            'enabled': False,
        }
        rawdata = {}
        self.assertEqual(insert.table, 'host_config')
        self.assertEqual(insert.data, data)
        self.assertEqual(insert.rawdata, rawdata)

    def test_edit_host_no_change(self):
        kojihub.get_host = mock.MagicMock()
        kojihub.get_host.return_value = self.hostinfo
        self.context_db.event_id = 42
        self.context_db.session.user_id = 23

        r = self.exports.editHost('hostname')

        self.assertFalse(r)
        kojihub.get_host.assert_called_once_with('hostname', strict=True)

        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.inserts), 0)
