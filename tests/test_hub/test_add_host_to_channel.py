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
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
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

    @mock.patch('kojihub.get_channel')
    @mock.patch('kojihub.list_channels')
    @mock.patch('kojihub.get_channel_id')
    @mock.patch('kojihub.get_host')
    def test_valid(self, get_host, get_channel_id, list_channels, get_channel):
        name = 'hostname'
        cname = 'channel_name'
        get_host.return_value = {'id': 123, 'name': name}
        get_channel_id.return_value = 456
        list_channels.return_value = [{'id': 1, 'name': 'default'}]
        get_channel.return_value = {'enabled': True}

        kojihub.add_host_to_channel(name, cname, create=False)

        get_host.assert_called_once_with(name)
        get_channel.assert_called_once_with(456)
        get_channel_id.assert_called_once_with(cname, create=False)
        list_channels.assert_called_once_with(123)

        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        data = {
            'host_id': 123,
            'channel_id': 456,
            'creator_id': 23,
            'create_event': 42,
        }
        self.assertEqual(insert.table, 'host_channels')
        self.assertEqual(insert.data, data)
        self.assertEqual(insert.rawdata, {})

    @mock.patch('kojihub.list_channels')
    @mock.patch('kojihub.get_channel_id')
    @mock.patch('kojihub.get_host')
    def test_no_host(self, get_host, get_channel_id, list_channels):
        name = 'hostname'
        cname = 'channel_name'
        get_host.return_value = None

        with self.assertRaises(koji.GenericError):
            kojihub.add_host_to_channel(name, cname, create=False)

        get_host.assert_called_once_with(name)
        self.assertEqual(len(self.inserts), 0)

    @mock.patch('kojihub.get_channel_id')
    @mock.patch('kojihub.get_host')
    def test_no_channel(self, get_host, get_channel_id):
        name = 'hostname'
        cname = 'channel_name'
        get_host.return_value = {'id': 123, 'name': name}
        get_channel_id.return_value = None

        with self.assertRaises(koji.GenericError):
            kojihub.add_host_to_channel(name, cname, create=False)

        get_host.assert_called_once_with(name)
        get_channel_id.assert_called_once_with(cname, create=False)
        self.assertEqual(len(self.inserts), 0)

    @mock.patch('kojihub.verify_name_internal')
    @mock.patch('kojihub.get_channel')
    @mock.patch('kojihub.list_channels')
    @mock.patch('kojihub.get_channel_id')
    @mock.patch('kojihub.get_host')
    def test_no_channel_create(self, get_host, get_channel_id, list_channels, get_channel,
                               verify_name_internal):
        name = 'hostname'
        cname = 'channel_name'
        get_host.return_value = {'id': 123, 'name': name}
        get_channel_id.return_value = 456
        list_channels.return_value = [{'id': 1, 'name': 'default'}]
        get_channel.return_value = {'enabled': True}
        verify_name_internal.return_value = None

        kojihub.add_host_to_channel(name, cname, create=True)

        get_host.assert_called_once_with(name)
        get_channel.assert_called_once_with(456)
        get_channel_id.assert_called_once_with(cname, create=True)
        list_channels.assert_called_once_with(123)

        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        data = {
            'host_id': 123,
            'channel_id': 456,
            'creator_id': 23,
            'create_event': 42,
        }
        self.assertEqual(insert.table, 'host_channels')
        self.assertEqual(insert.data, data)
        self.assertEqual(insert.rawdata, {})

    @mock.patch('kojihub.get_channel')
    @mock.patch('kojihub.list_channels')
    @mock.patch('kojihub.get_channel_id')
    @mock.patch('kojihub.get_host')
    def test_exists(self, get_host, get_channel_id, list_channels, get_channel):
        name = 'hostname'
        cname = 'channel_name'
        get_host.return_value = {'id': 123, 'name': name}
        get_channel_id.return_value = 456
        list_channels.return_value = [{'id': 456, 'name': cname}]
        get_channel.return_value = {'enabled': True}

        with self.assertRaises(koji.GenericError):
            kojihub.add_host_to_channel(name, cname, create=False)

        get_host.assert_called_once_with(name)
        get_channel.assert_called_once_with(456)
        get_channel_id.assert_called_once_with(cname, create=False)
        list_channels.assert_called_once_with(123)
        self.assertEqual(len(self.inserts), 0)

    @mock.patch('kojihub.verify_name_internal')
    @mock.patch('kojihub.get_host')
    def test_channel_wrong_format(self, get_host, verify_name_internal):
        name = 'hostname'
        channel_name = 'test-channel+'
        get_host.return_value = {'id': 123, 'name': name}

        # name is longer as expected
        verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_host_to_channel(name, channel_name, create=True)

        # not except regex rules
        verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.add_host_to_channel(name, channel_name, create=True)
