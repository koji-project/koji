import unittest
import koji
import cgi

import mock
from io import BytesIO
from .loadwebindex import webidx
from koji.server import ServerRedirect


class TestHostEdit(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.assert_login = mock.patch.object(webidx, "_assertLogin").start()
        self.gen_html = mock.patch.object(webidx, '_genHTML').start()
        self.server = mock.MagicMock()
        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': None
        }
        self.host_id = '1'
        self.host_info = {'id': int(self.host_id), 'name': 'test-host', 'enabled': True}

    def tearDown(self):
        mock.patch.stopall()

    def get_fs(self, urlencode_data):
        urlencode_environ = {
            'CONTENT_LENGTH': str(len(urlencode_data)),
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'QUERY_STRING': '',
            'REQUEST_METHOD': 'POST',
        }
        data = BytesIO(urlencode_data)
        data.seek(0)
        return cgi.FieldStorage(fp=data, environ=urlencode_environ)

    def test_hostedit_exception_host_not_existing(self):
        """Test hostedit function raises exception when host ID not exists."""
        self.get_server.return_value = self.server
        self.server.getHost.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            webidx.hostedit(self.environ, self.host_id)
        self.assertEqual(str(cm.exception), f'no host with ID: {self.host_id}')
        self.server.getHost.assert_called_with(int(self.host_id))
        self.server.editHost.assert_not_called()
        self.server.listChannels.assert_not_called()
        self.server.removeHostFromChannel.assert_not_called()
        self.server.addHostToChannel.assert_not_called()
        self.server.listChannels.assert_not_called()

    def test_hostedit_save_case_valid(self):
        """Test hostedit function valid case (save)."""
        urlencode_data = b"save=True&arches=x86_64&capacity=1.0&description=test-desc&" \
                         b"comment=test-comment&enable=True&channels=default"
        fs = self.get_fs(urlencode_data)
        self.server.getHost.return_value = self.host_info
        self.server.editHost.return_value = True
        self.server.listChannels.return_value = [{'id': 2, 'name': 'test-channel'}]
        self.server.removeHostFromChannel.return_value = None
        self.server.addHostToChannel.return_value = None

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server

        with self.assertRaises(ServerRedirect):
            webidx.hostedit(self.environ, self.host_id)
        self.assertEqual(self.environ['koji.redirect'], f'hostinfo?hostID={self.host_id}')
        self.server.getHost.assert_called_with(int(self.host_id))
        self.server.editHost.assert_called_with(int(self.host_id), arches='x86_64', capacity=1.0,
                                                description='test-desc', comment='test-comment')
        self.server.listChannels.assert_called_with(hostID=int(self.host_id))
        self.server.removeHostFromChannel.assert_called_with(
            self.host_info['name'], 'test-channel')
        self.server.addHostToChannel.assert_called_with(self.host_info['name'], 'default')

    def test_hostedit_cancel_case_valid(self):
        """Test hostedit function valid case (cancel)."""
        urlencode_data = b"cancel=True"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.getHost.return_value = self.host_info

        with self.assertRaises(ServerRedirect):
            webidx.hostedit(self.environ, self.host_id)
        self.assertEqual(self.environ['koji.redirect'], f'hostinfo?hostID={self.host_id}')
        self.server.getHost.assert_called_with(int(self.host_id))
        self.server.editHost.assert_not_called()
        self.server.listChannels.assert_not_called()
        self.server.removeHostFromChannel.assert_not_called()
        self.server.addHostToChannel.assert_not_called()
        self.server.listChannels.assert_not_called()

    def test_hostedit_another_case(self):
        """Test hostedit function valid case (another)."""
        urlencode_data = b"another=True"
        fs = self.get_fs(urlencode_data)

        def __get_server(env):
            env['koji.session'] = self.server
            env['koji.form'] = fs
            return self.server

        self.get_server.side_effect = __get_server
        self.server.getHost.return_value = self.host_info
        self.server.listChannels.side_effect = [
            [{'id': 1, 'name': 'test-channel-1'},
             {'id': 2, 'name': 'test-channel-2'},
             {'id': 3, 'name': 'test-channel-3'}],
            [{'id': 1, 'name': 'test-channel-1'},
             {'id': 3, 'name': 'test-channel-3'}]
        ]

        webidx.hostedit(self.environ, self.host_id)
        self.server.getHost.assert_called_with(int(self.host_id))
        self.server.editHost.assert_not_called()
        self.server.removeHostFromChannel.assert_not_called()
        self.server.addHostToChannel.assert_not_called()
        self.server.listChannels.assert_has_calls(([mock.call(),
                                                    mock.call(hostID=int(self.host_id))]))
