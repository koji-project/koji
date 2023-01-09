from __future__ import absolute_import

import mock
import six
import unittest

from koji_cli.commands import handle_add_host_to_channel
from . import utils


class TestAddHostToChannel(utils.CliTestCase):

    def setUp(self):
        self.maxDiff = None
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s add-host-to-channel [options] <hostname> <channel>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_add_host_to_channel(self, stdout):
        host = 'host'
        host_info = mock.ANY
        channel = 'channel'
        channel_info = mock.ANY
        args = [host, channel]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getChannel.return_value = channel_info
        session.getHost.return_value = host_info
        # Run it and check immediate output
        # args: host, channel
        # expected: success
        rv = handle_add_host_to_channel(options, session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(session, options)
        session.getChannel.assert_called_once_with(channel)
        session.getHost.assert_called_once_with(host)
        session.addHostToChannel.assert_called_once_with(host, channel)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_add_host_to_channel_list(self, stdout):
        list_arg = '--list'
        args = [list_arg]
        channel_infos = [{'name': 'channel1'}, {'name': 'channel2'}]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.listChannels.return_value = channel_infos
        # Run it and check immediate output
        # args: --list
        # expected: list all channel names
        rv = handle_add_host_to_channel(options, session, args)
        actual = stdout.getvalue()
        expected = 'channel1\nchannel2\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(session, options)
        session.listChannels.assert_called_once()
        session.getChannel.assert_not_called()
        session.getHost.assert_not_called()
        session.addHostToChannel.assert_not_called()
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_add_host_to_channel_new_and_force(self, stdout):
        host = 'host'
        host_info = mock.ANY
        channel = 'channel'
        new_arg = '--new'
        force_arg = '--force'
        args = [host, channel, new_arg, force_arg]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getHost.return_value = host_info
        # Run it and check immediate output
        # args: host, channel, --new
        # expected: success
        rv = handle_add_host_to_channel(options, session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(session, options)
        session.getChannel.assert_not_called()
        session.getHost.assert_called_once_with(host)
        session.addHostToChannel.assert_called_once_with(host, channel, create=True, force=True)
        self.assertNotEqual(rv, 1)

    def test_handle_add_host_to_channel_no_channel(self):
        host = 'host'
        channel = 'channel'
        channel_info = None
        arguments = [host, channel]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getChannel.return_value = channel_info
        # Run it and check immediate output
        # args: host, channel
        # expected: failed, channel not found
        self.assert_system_exit(
            handle_add_host_to_channel,
            options, session, arguments,
            stdout='',
            stderr='No such channel: channel\n',
            exit_code=1,
            activate_session=None)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(session, options)
        session.getChannel.assert_called_once_with(channel)
        session.getHost.assert_not_called()
        session.addHostToChannel.assert_not_called()

    def test_handle_add_host_to_channel_no_host(self):
        host = 'host'
        host_info = None
        channel = 'channel'
        channel_info = mock.ANY
        arguments = [host, channel]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getChannel.return_value = channel_info
        session.getHost.return_value = host_info
        # Run it and check immediate output
        # args: host, channel
        # expected: success
        self.assert_system_exit(
            handle_add_host_to_channel,
            options, session, arguments,
            stdout='',
            stderr='No such host: host\n',
            exit_code=1,
            activate_session=None)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(session, options)
        session.getChannel.assert_called_once_with(channel)
        session.getHost.assert_called_once_with(host)
        session.addHostToChannel.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_host_to_channel_no_args(
            self, activate_session_mock, stderr, stdout):
        arguments = []
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        # args: _empty_
        # expected: failed, help msg shows
        self.assert_system_exit(
            handle_add_host_to_channel,
            options, session, arguments,
            stdout='',
            stderr=self.format_error_message("Please specify a hostname and a channel"),
            exit_code=2,
            activate_session=None)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        session.getHost.assert_not_called()
        session.getChannel.assert_not_called()
        session.listChannels.assert_not_called()
        session.addHostToChannel.assert_not_called()

    def test_handle_add_host_to_channel_help(self):
        self.assert_help(
            handle_add_host_to_channel,
            """Usage: %s add-host-to-channel [options] <hostname> <channel>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
  --new       Create channel if needed
  --force     force added, if possible
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
