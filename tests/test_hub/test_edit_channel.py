import unittest

import mock

import koji
import kojihub

UP = kojihub.UpdateProcessor
IP = kojihub.InsertProcessor


class TestEditChannel(unittest.TestCase):
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
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.context = mock.patch('kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.exports = kojihub.RootExports()
        self.channel_name = 'test-channel'
        self.channel_name_new = 'test-channel-2'

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('kojihub.verify_name_internal')
    @mock.patch('kojihub.get_channel')
    def test_edit_channel_missing(self, get_channel, verify_name_internal):
        expected = 'Invalid type for channelInfo: %s' % self.channel_name
        get_channel.side_effect = koji.GenericError(expected)
        with self.assertRaises(koji.GenericError) as ex:
            self.exports.editChannel(self.channel_name, name=self.channel_name_new)
        get_channel.assert_called_once_with(self.channel_name, strict=True)
        self.assertEqual(self.inserts, [])
        self.assertEqual(self.updates, [])
        self.assertEqual(expected, str(ex.exception))

    @mock.patch('kojihub.verify_name_internal')
    @mock.patch('kojihub.get_channel')
    def test_edit_channel_already_exists(self, get_channel, verify_name_internal):
        verify_name_internal.return_value = None
        get_channel.side_effect = [
            {
                'id': 123,
                'name': self.channel_name,
                'description': 'description',
            },
            {
                'id': 124,
                'name': self.channel_name_new,
                'description': 'description',
            }
        ]
        with self.assertRaises(koji.GenericError) as ex:
            self.exports.editChannel(self.channel_name, name=self.channel_name_new)
        expected_calls = [mock.call(self.channel_name, strict=True),
                          mock.call(self.channel_name_new, strict=False)]
        get_channel.assert_has_calls(expected_calls)
        self.assertEqual(self.inserts, [])
        self.assertEqual(self.updates, [])
        self.assertEqual('channel %s already exists (id=124)' % self.channel_name_new,
                         str(ex.exception))

    @mock.patch('kojihub.verify_name_internal')
    @mock.patch('kojihub.get_channel')
    def test_edit_channel_valid(self, get_channel, verify_name_internal):
        verify_name_internal.return_value = None
        kojihub.get_channel.side_effect = [{
            'id': 123,
            'name': self.channel_name,
            'description': 'description',
        },
            {}]

        r = self.exports.editChannel(self.channel_name, name=self.channel_name_new,
                                     description='description_new')
        self.assertTrue(r)
        expected_calls = [mock.call(self.channel_name, strict=True),
                          mock.call(self.channel_name_new, strict=False)]
        get_channel.assert_has_calls(expected_calls)

        self.assertEqual(len(self.updates), 1)
        values = {'channelID': 123}
        clauses = ['id = %(channelID)i']

        update = self.updates[0]
        self.assertEqual(update.table, 'channels')
        self.assertEqual(update.values, values)
        self.assertEqual(update.clauses, clauses)

    @mock.patch('kojihub.verify_name_internal')
    @mock.patch('kojihub.get_channel')
    def test_edit_channel_wrong_format(self, get_channel, verify_name_internal):
        channel_name_new = 'test-channel+'
        get_channel.return_value = {'id': 123,
                                    'name': self.channel_name,
                                    'description': 'description',
                                    }

        # name is longer as expected
        verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.editChannel(self.channel_name, name=channel_name_new)

        # not except regex rules
        verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.editChannel(self.channel_name, name=channel_name_new)
