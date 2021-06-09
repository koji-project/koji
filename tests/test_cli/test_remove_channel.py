from __future__ import absolute_import

import unittest

import six
import mock

from koji_cli.commands import handle_remove_channel
from . import utils


class TestRemoveChannel(utils.CliTestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.channel_name = 'test-channel'
        self.description = 'description'
        self.channel_info = {
            'id': 123,
            'name': self.channel_name,
            'description': self.description,
        }
        self.maxDiff = None

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_channel(self, activate_session_mock, stdout):
        self.session.getChannel.return_value = self.channel_info
        rv = handle_remove_channel(self.options, self.session, [self.channel_name])
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getChannel.assert_called_once_with(self.channel_name)
        self.session.removeChannel.assert_called_once_with(self.channel_name, force=None)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_channel_force(self, activate_session_mock, stdout):
        self.session.getChannel.return_value = self.channel_info
        rv = handle_remove_channel(self.options, self.session, ['--force', self.channel_name])
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getChannel.assert_called_once_with(self.channel_name)
        self.session.removeChannel.assert_called_once_with(self.channel_name, force=True)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_channel_no_channel(
            self, activate_session_mock, stderr):
        channel_info = None

        self.session.getChannel.return_value = channel_info
        with self.assertRaises(SystemExit) as ex:
            handle_remove_channel(self.options, self.session, [self.channel_name])
        self.assertExitCode(ex, 1)
        actual = stderr.getvalue()
        expected = 'No such channel: %s\n' % self.channel_name
        self.assertMultiLineEqual(actual, expected)
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getChannel.assert_called_once_with(self.channel_name)
        self.session.removeChannel.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_channel_help(
            self, activate_session_mock, stderr, stdout):
        with self.assertRaises(SystemExit) as ex:
            handle_remove_channel(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = ''
        expected_stderr = """Usage: %s remove-channel [options] <channel>
(Specify the --help global option for a list of other help options)

%s: error: Incorrect number of arguments
""" % (self.progname, self.progname)
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)
        activate_session_mock.assert_not_called()
        self.session.getChannel.assert_not_called()
        self.session.removeChannel.assert_not_called()


if __name__ == '__main__':
    unittest.main()
