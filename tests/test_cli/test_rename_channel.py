from __future__ import absolute_import

import unittest

import mock
import six

from koji_cli.commands import handle_rename_channel
from . import utils


class TestRenameChannel(utils.CliTestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.channel_name_old = 'old-channel'
        self.channel_name_new = 'new-channel'
        self.description = 'description'
        self.channel_info = {
            'id': 123,
            'name': self.channel_name_old,
            'description': self.description,
        }
        self.maxDiff = None

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_rename_channel(self, activate_session_mock, stdout):
        args = [self.channel_name_old, self.channel_name_new]
        self.session.getChannel.return_value = self.channel_info
        # Run it and check immediate output
        # args: old_name, new_name
        # expected: success
        rv = handle_rename_channel(self.options, self.session, args)
        depr_warn = 'rename-channel is deprecated and will be removed in 1.28'
        self.assert_console_message(stdout, depr_warn, regex=True)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getChannel.assert_called_once_with(self.channel_name_old)
        self.session.renameChannel.assert_called_once_with(self.channel_name_old,
                                                           self.channel_name_new)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_rename_channel_no_channel(self, activate_session_mock, stderr, stdout):
        channel_info = None
        args = [self.channel_name_old, self.channel_name_new]
        self.session.getChannel.return_value = channel_info
        # Run it and check immediate output
        # args: old_name, new_name
        # expected: failed: no such channel
        with self.assertRaises(SystemExit) as ex:
            handle_rename_channel(self.options, self.session, args)
        self.assertExitCode(ex, 1)
        expected = 'No such channel: %s' % self.channel_name_old
        depr_warn = 'rename-channel is deprecated and will be removed in 1.28'
        self.assert_console_message(stderr, expected, wipe=False, regex=True)
        self.assert_console_message(stdout, depr_warn, wipe=False, regex=True)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getChannel.assert_called_once_with(self.channel_name_old)
        self.session.renameChannel.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_rename_channel_more_args(self, activate_session_mock, stderr, stdout):
        args = [self.channel_name_old, self.channel_name_new, 'extra-arg']
        with self.assertRaises(SystemExit) as ex:
            handle_rename_channel(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        expected = 'Incorrect number of arguments'
        depr_warn = 'rename-channel is deprecated and will be removed in 1.28'
        self.assert_console_message(stderr, expected, wipe=False, regex=True)
        self.assert_console_message(stdout, depr_warn, wipe=False, regex=True)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        self.session.getChannel.assert_not_called()
        self.session.renameChannel.assert_not_called()

    def test_handle_rename_channel_help(self):
        self.assert_help(
            handle_rename_channel,
            """Usage: %s rename-channel [options] <old-name> <new-name>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
