import unittest

from unittest import mock

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
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.exports = kojihub.RootExports()
        self.channel_name = 'test-channel'
        self.channel_name_new = 'test-channel-2'
        self.channel_info = {'id': 123, 'name': self.channel_name, 'description': 'description',
                             'comment': 'comment'}
        self.get_channel = mock.patch('kojihub.kojihub.get_channel').start()
        self.verify_name_internal = mock.patch('kojihub.kojihub.verify_name_internal').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_edit_channel_missing(self):
        expected = 'Invalid type for channelInfo: %s' % self.channel_name
        self.get_channel.side_effect = koji.GenericError(expected)
        with self.assertRaises(koji.GenericError) as ex:
            self.exports.editChannel(self.channel_name, name=self.channel_name_new)
        self.get_channel.assert_called_once_with(self.channel_name, strict=True)
        self.assertEqual(self.inserts, [])
        self.assertEqual(self.updates, [])
        self.assertEqual(expected, str(ex.exception))

    def test_edit_channel_already_exists(self):
        self.verify_name_internal.return_value = None
        self.get_channel.side_effect = [
            self.channel_info,
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
        self.get_channel.assert_has_calls(expected_calls)
        self.assertEqual(self.inserts, [])
        self.assertEqual(self.updates, [])
        self.assertEqual(f'channel {self.channel_name_new} already exists (id=124)',
                         str(ex.exception))

    def test_edit_channel_valid(self):
        self.verify_name_internal.return_value = None
        self.get_channel.side_effect = [self.channel_info, {}]

        r = self.exports.editChannel(self.channel_name, name=self.channel_name_new,
                                     description='description_new')
        self.assertTrue(r)
        expected_calls = [mock.call(self.channel_name, strict=True),
                          mock.call(self.channel_name_new, strict=False)]
        self.get_channel.assert_has_calls(expected_calls)

        self.assertEqual(len(self.updates), 1)
        values = {'channelID': 123}
        clauses = ['id = %(channelID)i']

        update = self.updates[0]
        self.assertEqual(update.table, 'channels')
        self.assertEqual(update.values, values)
        self.assertEqual(update.clauses, clauses)

    def test_edit_channel_wrong_name(self):
        channel_name_new = 'test-channel+'
        self.get_channel.return_value = self.channel_info

        # name is longer as expected
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.editChannel(self.channel_name, name=channel_name_new)

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.editChannel(self.channel_name, name=channel_name_new)

    def test_edit_channel_no_change(self):
        self.verify_name_internal.return_value = None
        self.get_channel.return_value = self.channel_info

        r = self.exports.editChannel(self.channel_name, description='description')
        self.assertFalse(r)
        self.assertEqual(self.updates, [])
        self.get_channel.assert_called_once_with(self.channel_name, strict=True)
        self.verify_name_internal.assert_not_called()

    def test_edit_channel_wrong_format_new_name(self):
        channel_name_new = 13568
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.editChannel(self.channel_name, name=channel_name_new)
        self.assertEqual(self.updates, [])
        self.get_channel.assert_called_once_with(self.channel_name, strict=True)
        self.verify_name_internal.assert_called_once_with(channel_name_new)

    def test_edit_channel_wrong_format_description(self):
        description = ['description']
        self.get_channel.return_value = self.channel_info
        with self.assertRaises(koji.ParameterError) as ex:
            self.exports.editChannel(self.channel_name, description=description)
        self.assertEqual(self.updates, [])
        self.assertEqual(f"Invalid type for value '{description}': {type(description)}, "
                         f"expected type <class 'str'>", str(ex.exception))
        self.get_channel.assert_called_once_with(self.channel_name, strict=True)
        self.verify_name_internal.assert_not_called()

    def test_edit_channel_wrong_format_comment(self):
        comment = ['comment']
        self.get_channel.return_value = self.channel_info
        with self.assertRaises(koji.ParameterError) as ex:
            self.exports.editChannel(self.channel_name, comment=comment)
        self.assertEqual(self.updates, [])
        self.assertEqual(f"Invalid type for value '{comment}': {type(comment)}, "
                         f"expected type <class 'str'>", str(ex.exception))
        self.get_channel.assert_called_once_with(self.channel_name, strict=True)
        self.verify_name_internal.assert_not_called()
