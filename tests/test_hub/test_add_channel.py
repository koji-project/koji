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

    def tearDown(self):
        mock.patch.stopall()

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = self.insert_execute
        self.inserts.append(insert)
        return insert

    @mock.patch('kojihub.verify_name_internal')
    @mock.patch('kojihub.get_channel')
    @mock.patch('kojihub._singleValue')
    def test_add_channel_exists(self, _singleValue, get_channel, verify_name_internal):
        verify_name_internal.return_value = None
        get_channel.return_value = {'id': 123, 'name': self.channel_name}
        with self.assertRaises(koji.GenericError):
            self.exports.addChannel(self.channel_name)
        get_channel.assert_called_once_with(self.channel_name, strict=False)
        _singleValue.assert_not_called()
        self.assertEqual(len(self.inserts), 0)

    @mock.patch('kojihub.verify_name_internal')
    @mock.patch('kojihub.get_channel')
    @mock.patch('kojihub._singleValue')
    def test_add_channel_valid(self, _singleValue, get_channel, verify_name_internal):
        get_channel.return_value = {}
        _singleValue.side_effect = [12]
        verify_name_internal.return_value = None

        r = self.exports.addChannel(self.channel_name, description=self.description)
        self.assertEqual(r, 12)
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.data['name'], self.channel_name)
        self.assertEqual(insert.data['id'], 12)
        self.assertEqual(insert.data['description'], self.description)
        self.assertEqual(insert.table, 'channels')

        self.context.session.assertPerm.assert_called_once_with('admin')
        get_channel.assert_called_once_with(self.channel_name, strict=False)
        self.assertEqual(_singleValue.call_count, 1)
        _singleValue.assert_has_calls([
            mock.call("SELECT nextval('channels_id_seq')", strict=True)
        ])

    @mock.patch('kojihub.verify_name_internal')
    def test_add_channel_wrong_format(self, verify_name_internal):
        # name is longer as expected
        channel_name = 'test-channel+'
        verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.addChannel(channel_name)

        # not except regex rules
        verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.addChannel(channel_name)
