import unittest

import StringIO as stringio

import os

import sys

import mock

import loadcli

cli = loadcli.cli


class TestRemoveChannel(unittest.TestCase):

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    @mock.patch('koji_cli.activate_session')
    def test_handle_remove_channel(self, activate_session_mock, stdout):
        channel = 'channel'
        channel_info = mock.ANY
        args = [channel]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getChannel.return_value = channel_info
        # Run it and check immediate output
        # args: channel
        # expected: success
        rv = cli.handle_remove_channel(options, session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session)
        session.getChannel.assert_called_once_with(channel)
        session.removeChannel.assert_called_once_with(channel, force=None)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    @mock.patch('koji_cli.activate_session')
    def test_handle_remove_channel_force(self, activate_session_mock, stdout):
        channel = 'channel'
        channel_info = mock.ANY
        force_arg = '--force'
        args = [force_arg, channel]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getChannel.return_value = channel_info
        # Run it and check immediate output
        # args: --force, channel
        # expected: success
        rv = cli.handle_remove_channel(options, session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session)
        session.getChannel.assert_called_once_with(channel)
        session.removeChannel.assert_called_once_with(channel, force=True)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    @mock.patch('koji_cli.activate_session')
    def test_handle_remove_channel_no_channel(
            self, activate_session_mock, stdout):
        channel = 'channel'
        channel_info = None
        args = [channel]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getChannel.return_value = channel_info
        # Run it and check immediate output
        # args: channel
        # expected: failed: no such channel
        rv = cli.handle_remove_channel(options, session, args)
        actual = stdout.getvalue()
        expected = 'No such channel: channel\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session)
        session.getChannel.assert_called_once_with(channel)
        session.removeChannel.assert_not_called()
        self.assertEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    @mock.patch('sys.stderr', new_callable=stringio.StringIO)
    @mock.patch('koji_cli.activate_session')
    def test_handle_remove_channel_help(
            self, activate_session_mock, stderr, stdout):
        args = []
        options = mock.MagicMock()
        progname = os.path.basename(sys.argv[0]) or 'koji'

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as cm:
            cli.handle_remove_channel(options, session, args)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = ''
        expected_stderr = """Usage: %s remove-channel [options] channel
(Specify the --help global option for a list of other help options)

%s: error: Incorrect number of arguments
""" % (progname, progname)
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        session.getChannel.assert_not_called()
        session.removeChannel.assert_not_called()
        self.assertEqual(cm.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
