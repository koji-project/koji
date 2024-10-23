import unittest

from unittest import mock

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
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context_db = mock.patch('kojihub.db.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context_db.session.assertLogin = mock.MagicMock()
        self.context.session.assertPerm = mock.MagicMock()
        self.context_db.event_id = 42
        self.context_db.session.user_id = 23
        self.context.opts = {'HostPrincipalFormat': '-%s-'}
        self.exports = kojihub.RootExports()
        self.list_channels = mock.patch('kojihub.kojihub.list_channels').start()
        self.get_channel_id = mock.patch('kojihub.kojihub.get_channel_id').start()
        self.get_host = mock.patch('kojihub.kojihub.get_host').start()
        self.hostname = 'hostname'
        self.hostinfo = {'id': 123, 'name': self.hostname}
        self.channel_id = 234
        self.channelname = 'channelname'
        self.list_channels_output = [{'id': self.channel_id, 'name': self.channelname}]

    def tearDown(self):
        mock.patch.stopall()

    def test_valid(self):
        self.get_host.return_value = self.hostinfo
        self.get_channel_id.return_value = self.channel_id
        self.list_channels.return_value = self.list_channels_output

        kojihub.remove_host_from_channel(self.hostname, self.channelname)

        self.get_host.assert_called_once_with(self.hostname)
        self.get_channel_id.assert_called_once_with(self.channelname)
        self.list_channels.assert_called_once_with(self.hostinfo['id'])

        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        values = {
            'host_id': self.hostinfo['id'],
            'channel_id': self.channel_id,
        }
        clauses = [
            'host_id = %(host_id)i AND channel_id = %(channel_id)i',
            'active = TRUE',
        ]
        self.assertEqual(update.table, 'host_channels')
        self.assertEqual(update.values, values)
        self.assertEqual(update.clauses, clauses)

    def test_wrong_host(self):
        self.get_host.return_value = None

        with self.assertRaises(koji.GenericError):
            kojihub.remove_host_from_channel(self.hostname, self.channelname)

        self.get_host.assert_called_once_with(self.hostname)
        self.assertEqual(len(self.updates), 0)

    def test_wrong_channel(self):
        self.get_host.return_value = self.hostinfo
        self.get_channel_id.return_value = None
        self.list_channels.return_value = self.list_channels_output

        with self.assertRaises(koji.GenericError):
            kojihub.remove_host_from_channel(self.hostname, self.channelname)

        self.get_host.assert_called_once_with(self.hostname)
        self.get_channel_id.assert_called_once_with(self.channelname)
        self.assertEqual(len(self.updates), 0)

    def test_missing_record(self):
        self.get_host.return_value = self.hostinfo
        self.get_channel_id.return_value = self.channel_id
        self.list_channels.return_value = []

        with self.assertRaises(koji.GenericError):
            kojihub.remove_host_from_channel(self.hostname, self.channelname)

        self.get_host.assert_called_once_with(self.hostname)
        self.get_channel_id.assert_called_once_with(self.channelname)
        self.list_channels.assert_called_once_with(self.hostinfo['id'])
        self.assertEqual(len(self.updates), 0)
