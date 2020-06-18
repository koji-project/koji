import mock
import unittest

import koji
import kojihub

UP = kojihub.UpdateProcessor


class TestRemoveHostFromChannel(unittest.TestCase):
    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.UpdateProcessor = mock.patch('kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.context = mock.patch('kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.assertPerm = mock.MagicMock()
        self.context.event_id = 42
        self.context.session.user_id = 23
        self.context.opts = {'HostPrincipalFormat': '-%s-'}
        self.exports = kojihub.RootExports()

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('kojihub.list_channels')
    @mock.patch('kojihub.get_channel_id')
    @mock.patch('kojihub.get_host')
    def test_valid(self, get_host, get_channel_id, list_channels):
        get_host.return_value = {'id': 123, 'name': 'hostname'}
        get_channel_id.return_value = 234
        list_channels.return_value = [{'id': 234, 'name': 'channelname'}]

        kojihub.remove_host_from_channel('hostname', 'channelname')

        get_host.assert_called_once_with('hostname')
        get_channel_id.assert_called_once_with('channelname')
        list_channels.assert_called_once_with(123)

        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        values = {
            'host_id': 123,
            'channel_id': 234,
        }
        clauses = [
            'host_id = %(host_id)i AND channel_id = %(channel_id)i',
            'active = TRUE',
        ]
        self.assertEqual(update.table, 'host_channels')
        self.assertEqual(update.values, values)
        self.assertEqual(update.clauses, clauses)

    @mock.patch('kojihub.list_channels')
    @mock.patch('kojihub.get_channel_id')
    @mock.patch('kojihub.get_host')
    def test_wrong_host(self, get_host, get_channel_id, list_channels):
        get_host.return_value = None

        with self.assertRaises(koji.GenericError):
            kojihub.remove_host_from_channel('hostname', 'channelname')

        get_host.assert_called_once_with('hostname')
        self.assertEqual(len(self.updates), 0)

    @mock.patch('kojihub.list_channels')
    @mock.patch('kojihub.get_channel_id')
    @mock.patch('kojihub.get_host')
    def test_wrong_channel(self, get_host, get_channel_id, list_channels):
        get_host.return_value = {'id': 123, 'name': 'hostname'}
        get_channel_id.return_value = None
        list_channels.return_value = [{'id': 234, 'name': 'channelname'}]

        with self.assertRaises(koji.GenericError):
            kojihub.remove_host_from_channel('hostname', 'channelname')

        get_host.assert_called_once_with('hostname')
        get_channel_id.assert_called_once_with('channelname')
        self.assertEqual(len(self.updates), 0)

    @mock.patch('kojihub.list_channels')
    @mock.patch('kojihub.get_channel_id')
    @mock.patch('kojihub.get_host')
    def test_missing_record(self, get_host, get_channel_id, list_channels):
        get_host.return_value = {'id': 123, 'name': 'hostname'}
        get_channel_id.return_value = 234
        list_channels.return_value = []

        with self.assertRaises(koji.GenericError):
            kojihub.remove_host_from_channel('hostname', 'channelname')

        get_host.assert_called_once_with('hostname')
        get_channel_id.assert_called_once_with('channelname')
        list_channels.assert_called_once_with(123)
        self.assertEqual(len(self.updates), 0)
