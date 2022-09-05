import unittest

import mock

import koji
import kojihub

UP = kojihub.UpdateProcessor
IP = kojihub.InsertProcessor


class TestAddChannel(unittest.TestCase):

    def setUp(self):

        self.context = mock.patch('kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.exports = kojihub.RootExports()
        self.channel_name = 'test-channel'
        self.description = 'test-description'
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.insert_execute = mock.MagicMock()
        self.verify_name_internal = mock.patch('kojihub.verify_name_internal').start()
        self.get_channel = mock.patch('kojihub.get_channel').start()
        self.nextval = mock.patch('kojihub.nextval').start()

    def tearDown(self):
        mock.patch.stopall()

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = self.insert_execute
        self.inserts.append(insert)
        return insert

    def test_add_channel_exists(self):
        self.verify_name_internal.return_value = None
        self.get_channel.return_value = {'id': 123, 'name': self.channel_name}
        with self.assertRaises(koji.GenericError):
            self.exports.addChannel(self.channel_name)
        self.get_channel.assert_called_once_with(self.channel_name, strict=False)
        self.nextval.assert_not_called()
        self.assertEqual(len(self.inserts), 0)

    def test_add_channel_valid(self):
        self.get_channel.return_value = {}
        self.nextval.side_effect = [12]
        self.verify_name_internal.return_value = None

        r = self.exports.addChannel(self.channel_name, description=self.description)
        self.assertEqual(r, 12)
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.data['name'], self.channel_name)
        self.assertEqual(insert.data['id'], 12)
        self.assertEqual(insert.data['description'], self.description)
        self.assertEqual(insert.table, 'channels')

        self.context.session.assertPerm.assert_called_once_with('admin')
        self.get_channel.assert_called_once_with(self.channel_name, strict=False)
        self.assertEqual(self.nextval.call_count, 1)
        self.nextval.assert_called_once_with('channels_id_seq')

    def test_add_channel_wrong_name(self):
        # name is longer as expected
        channel_name = 'test-channel+'
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.addChannel(channel_name)

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.addChannel(channel_name)
