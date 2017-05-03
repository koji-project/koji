from __future__ import absolute_import
import unittest

import StringIO as stringio

import os

import sys

import mock

from . import loadcli

cli = loadcli.cli


class TestRenameChannel(unittest.TestCase):

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    @mock.patch('koji_cli.activate_session')
    def test_handle_rename_channel(self, activate_session_mock, stdout):
        old_name = 'old_name'
        new_name = 'new_name'
        channel_info = mock.ANY
        args = [old_name, new_name]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getChannel.return_value = channel_info
        # Run it and check immediate output
        # args: old_name, new_name
        # expected: success
        rv = cli.handle_rename_channel(options, session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session)
        session.getChannel.assert_called_once_with(old_name)
        session.renameChannel.assert_called_once_with(old_name, new_name)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    @mock.patch('koji_cli.activate_session')
    def test_handle_rename_channel_no_channel(
            self, activate_session_mock, stdout):
        old_name = 'old_name'
        new_name = 'new_name'
        channel_info = None
        args = [old_name, new_name]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getChannel.return_value = channel_info
        # Run it and check immediate output
        # args: old_name, new_name
        # expected: failed: no such channel
        rv = cli.handle_rename_channel(options, session, args)
        actual = stdout.getvalue()
        expected = 'No such channel: old_name\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session)
        session.getChannel.assert_called_once_with(old_name)
        session.renameChannel.assert_not_called()
        self.assertEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    @mock.patch('sys.stderr', new_callable=stringio.StringIO)
    @mock.patch('koji_cli.activate_session')
    def test_handle_rename_channel_help(
            self, activate_session_mock, stderr, stdout):
        args = []
        options = mock.MagicMock()
        progname = os.path.basename(sys.argv[0]) or 'koji'

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as cm:
            cli.handle_rename_channel(options, session, args)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = ''
        expected_stderr = """Usage: %s rename-channel [options] old-name new-name
(Specify the --help global option for a list of other help options)

%s: error: Incorrect number of arguments
""" % (progname, progname)
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        session.getChannel.assert_not_called()
        session.renameChannel.assert_not_called()
        self.assertEqual(cm.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
