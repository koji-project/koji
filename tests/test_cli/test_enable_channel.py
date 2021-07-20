from __future__ import absolute_import

import unittest

import mock
import six

import koji
from koji_cli.commands import handle_enable_channel
from . import utils


class TestEnableChannel(utils.CliTestCase):
    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s enable-channel [options] <channelname> [<channelname> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.channelinfo = [
            {'comment': None, 'description': None, 'enabled': False, 'id': 1,
             'name': 'test-channel'}
        ]

    def __vm(self, result):
        m = koji.VirtualCall('mcall_method', [], {})
        if isinstance(result, dict) and result.get('faultCode'):
            m._result = result
        else:
            m._result = (result,)
        return m

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_enable_channel(self, activate_session_mock, stdout, stderr):
        """Test enable-channel function"""
        options = mock.MagicMock()
        session = mock.MagicMock()

        mcall = session.multicall.return_value.__enter__.return_value

        mcall.getChannel.return_value = self.__vm(None)

        arguments = ['channel1', 'channel2']
        with self.assertRaises(SystemExit) as ex:
            handle_enable_channel(options, session, arguments)
        self.assertExitCode(ex, 1)
        activate_session_mock.assert_called_once()
        session.multicall.assert_called_once()
        session.enableChannel.assert_not_called()
        expect = ''
        for host in arguments:
            expect += "No such channel: %s\n" % host
        stderr_exp = "No changes made. Please correct the command line.\n"
        self.assert_console_message(stdout, expect)
        self.assert_console_message(stderr, stderr_exp)

        # reset session mocks
        activate_session_mock.reset_mock()
        session.multicall.reset_mock()
        session.enableChannel.reset_mock()
        mcall = session.multicall.return_value.__enter__.return_value

        mcall.getChannel.return_value = self.__vm(self.channelinfo)

        arguments = ['channel1', 'channel2', '--comment', 'enable channel test']
        handle_enable_channel(options, session, arguments)
        activate_session_mock.assert_called_once()
        self.assertEqual(2, session.multicall.call_count)
        self.assert_console_message(stdout, '')

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_enable_host_no_argument(self, activate_session_mock, stdout):
        """Test enable-channel function without arguments"""
        options = mock.MagicMock()
        session = mock.MagicMock()

        session.getChannel.return_value = None
        session.multicall.return_value = [[None]]
        session.enableChannel.return_value = True

        expected = self.format_error_message("At least one channel must be specified")
        self.assert_system_exit(
            handle_enable_channel,
            options,
            session,
            [],
            stderr=expected,
            activate_session=None)

        activate_session_mock.assert_not_called()
        session.getChannel.assert_not_called()
        session.multicall.assert_not_called()
        session.enableChannel.assert_not_called()

    def test_handle_enable_channel_help(self):
        """Test enable-channel help message"""
        self.assert_help(
            handle_enable_channel,
            """Usage: %s enable-channel [options] <channelname> [<channelname> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help         show this help message and exit
  --comment=COMMENT  Comment indicating why the channel(s) are being enabled
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
