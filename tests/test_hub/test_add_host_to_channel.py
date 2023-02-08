import unittest

import mock

import koji
import kojihub

IP = kojihub.InsertProcessor


class TestAddHostToChannel(unittest.TestCase):
    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def setUp(self):
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
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
        self.get_channel = mock.patch('kojihub.kojihub.get_channel').start()
        self.list_channels = mock.patch('kojihub.kojihub.list_channels').start()
        self.get_channel_id = mock.patch('kojihub.kojihub.get_channel_id').start()
        self.get_host = mock.patch('kojihub.kojihub.get_host').start()
        self.verify_name_internal = mock.patch('kojihub.kojihub.verify_name_internal').start()
        self.cname = 'channel_name'
        self.name = 'hostname'
        self.host_info = {'id': 123, 'name': self.name}
        self.channel_id = 456
        self.list_channels_dict = [{'id': 1, 'name': 'default'}]
        self.channel_info = {'enabled': True}

    def tearDown(self):
        mock.patch.stopall()

    def test_valid(self):
        self.get_host.return_value = self.host_info
        self.get_channel_id.return_value = self.channel_id
        self.list_channels.return_value = self.list_channels_dict
        self.get_channel.return_value = self.channel_info

        kojihub.add_host_to_channel(self.name, self.cname, create=False)

        self.get_host.assert_called_once_with(self.name)
        self.get_channel.assert_called_once_with(self.channel_id)
        self.get_channel_id.assert_called_once_with(self.cname, create=False)
        self.list_channels.assert_called_once_with(self.host_info['id'])
        self.verify_name_internal.assert_not_called()

        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        data = {
            'host_id': self.host_info['id'],
            'channel_id': self.channel_id,
            'creator_id': 23,
            'create_event': 42,
        }
        self.assertEqual(insert.table, 'host_channels')
        self.assertEqual(insert.data, data)
        self.assertEqual(insert.rawdata, {})

    def test_no_host(self):
        self.get_host.return_value = None

        with self.assertRaises(koji.GenericError) as ex:
            kojihub.add_host_to_channel(self.name, self.cname, create=False)

        self.get_host.assert_called_once_with(self.name)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(f"host does not exist: {self.name}", str(ex.exception))

    def test_no_channel(self):
        self.get_host.return_value = self.host_info
        self.get_channel_id.return_value = None

        with self.assertRaises(koji.GenericError) as ex:
            kojihub.add_host_to_channel(self.name, self.cname, create=False)

        self.get_host.assert_called_once_with(self.name)
        self.get_channel_id.assert_called_once_with(self.cname, create=False)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(f"channel does not exist: {self.cname}", str(ex.exception))

    def test_no_channel_create(self):
        self.get_host.return_value = self.host_info
        self.get_channel_id.return_value = self.channel_id
        self.list_channels.return_value = self.list_channels_dict
        self.get_channel.return_value = self.get_channel
        self.verify_name_internal.return_value = None

        kojihub.add_host_to_channel(self.name, self.cname, create=True)

        self.get_host.assert_called_once_with(self.name)
        self.get_channel.assert_called_once_with(self.channel_id)
        self.get_channel_id.assert_called_once_with(self.cname, create=True)
        self.list_channels.assert_called_once_with(self.host_info['id'])
        self.verify_name_internal.assert_called_once_with(self.cname)

        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        data = {
            'host_id': self.host_info['id'],
            'channel_id': self.channel_id,
            'creator_id': 23,
            'create_event': 42,
        }
        self.assertEqual(insert.table, 'host_channels')
        self.assertEqual(insert.data, data)
        self.assertEqual(insert.rawdata, {})

    def test_exists(self):
        self.get_host.return_value = self.host_info
        self.get_channel_id.return_value = self.channel_id
        self.list_channels.return_value = [{'id': self.channel_id, 'name': self.cname}]
        self.get_channel.return_value = self.channel_info

        with self.assertRaises(koji.GenericError) as ex:
            kojihub.add_host_to_channel(self.name, self.cname, create=False)

        self.get_host.assert_called_once_with(self.name)
        self.get_channel.assert_called_once_with(self.channel_id)
        self.get_channel_id.assert_called_once_with(self.cname, create=False)
        self.list_channels.assert_called_once_with(self.host_info['id'])
        self.verify_name_internal.assert_not_called()
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(f"host {self.name} is already subscribed to the {self.cname} channel",
                         str(ex.exception))

    def test_channel_wrong_format(self):
        channel_name = 'test-channel+'
        self.get_host.return_value = self.host_info

        # name is longer as expected
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_host_to_channel(self.name, channel_name, create=True)

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_host_to_channel(self.name, channel_name, create=True)

    def test_channel_disabled_without_force(self):
        self.get_host.return_value = self.host_info
        self.get_channel_id.return_value = self.channel_id
        self.get_channel.return_value = {'id': 456, 'enabled': False}

        with self.assertRaises(koji.GenericError) as ex:
            kojihub.add_host_to_channel(self.name, self.cname, create=False)

        self.get_host.assert_called_once_with(self.name)
        self.get_channel.assert_called_once_with(self.channel_id)
        self.get_channel_id.assert_called_once_with(self.cname, create=False)
        self.list_channels.assert_not_called()
        self.verify_name_internal.assert_not_called()
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(f"channel {self.cname} is disabled", str(ex.exception))

    def test_disable_with_force(self):
        self.get_host.return_value = self.host_info
        self.get_channel_id.return_value = self.channel_id
        self.list_channels.return_value = self.list_channels_dict

        kojihub.add_host_to_channel(self.name, self.cname, create=False, force=True)

        self.get_host.assert_called_once_with(self.name)
        self.get_channel.assert_not_called()
        self.get_channel_id.assert_called_once_with(self.cname, create=False)
        self.list_channels.assert_called_once_with(self.host_info['id'])
        self.verify_name_internal.assert_not_called()

        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        data = {
            'host_id': self.host_info['id'],
            'channel_id': self.channel_id,
            'creator_id': 23,
            'create_event': 42,
        }
        self.assertEqual(insert.table, 'host_channels')
        self.assertEqual(insert.data, data)
        self.assertEqual(insert.rawdata, {})
