from __future__ import absolute_import
import mock
import os
import six
import sys
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_remove_host_from_channel
from . import utils

class TestRemoveHostFromChannel(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_host_from_channel(
            self, activate_session_mock, stdout):
        host = 'host'
        host_info = {'id': 1}
        channel = 'channel'
        args = [host, channel]
        channel_infos = [{'name': 'channel'}, {'name': 'other_channel'}]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getHost.return_value = host_info
        session.listChannels.return_value = channel_infos
        # Run it and check immediate output
        # args: host, channel
        # expected: success
        rv = handle_remove_host_from_channel(options, session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.getHost.assert_called_once_with(host)
        session.listChannels.assert_called_once_with(host_info['id'])
        session.removeHostFromChannel.assert_called_once_with(host, channel)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_host_from_channel_no_host(
            self, activate_session_mock, stderr):
        host = 'host'
        host_info = None
        channel = 'channel'
        args = [host, channel]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getHost.return_value = host_info
        # Run it and check immediate output
        # args: host, channel
        # expected: failed: no such host
        with self.assertRaises(SystemExit) as ex:
            handle_remove_host_from_channel(options, session, args)
        self.assertExitCode(ex, 1)
        actual = stderr.getvalue()
        expected = 'No such host: host\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.getHost.assert_called_once_with(host)
        session.listChannels.assert_not_called()
        session.removeHostFromChannel.assert_not_called()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_host_from_channel_not_a_member(
            self, activate_session_mock, stderr):
        host = 'host'
        host_info = {'id': 1}
        channel = 'channel'
        args = [host, channel]
        channel_infos = [{'name': 'other_channel1'},
                         {'name': 'other_channel2'}]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getHost.return_value = host_info
        session.listChannels.return_value = channel_infos
        # Run it and check immediate output
        # args: host, channel
        # expected: failed: host isn't belong to channel
        with self.assertRaises(SystemExit) as ex:
            handle_remove_host_from_channel(options, session, args)
        self.assertExitCode(ex, 1)
        actual = stderr.getvalue()
        expected = 'Host host is not a member of channel channel\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.getHost.assert_called_once_with(host)
        session.listChannels.assert_called_once_with(host_info['id'])
        session.removeHostFromChannel.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_host_from_channel_help(
            self, activate_session_mock, stderr, stdout):
        args = []
        options = mock.MagicMock()
        progname = os.path.basename(sys.argv[0]) or 'koji'

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        # args: _empty_
        # expected: failed, help msg shows
        with self.assertRaises(SystemExit) as ex:
            handle_remove_host_from_channel(options, session, args)
        self.assertExitCode(ex, 2)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = ''
        expected_stderr = """Usage: %s remove-host-from-channel [options] <hostname> <channel>
(Specify the --help global option for a list of other help options)

%s: error: Please specify a hostname and a channel
""" % (progname, progname)
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        session.getHost.assert_not_called()
        session.listChannels.assert_not_called()
        session.removeHostFromChannel.assert_not_called()


if __name__ == '__main__':
    unittest.main()
