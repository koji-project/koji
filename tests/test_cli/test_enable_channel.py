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
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
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

    def test_handle_enable_channel_no_such_channel(self):
        """Test enable-channel function"""
        mcall = self.session.multicall.return_value.__enter__.return_value

        mcall.getChannel.return_value = self.__vm(None)

        arguments = ['channel1', 'channel2']
        expect = ''
        for host in arguments:
            expect += "No such channel: %s\n" % host
        stderr_exp = "No changes made. Please correct the command line.\n"
        self.assert_system_exit(
            handle_enable_channel,
            self.options,
            self.session,
            arguments,
            stdout=expect,
            stderr=stderr_exp,
            activate_session=None,
            exit_code=1
        )
        self.activate_session_mock.assert_called_once()
        self.session.multicall.assert_called_once()
        self.session.enableChannel.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_enable_channel(self, stdout):
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.getChannel.return_value = self.__vm(self.channelinfo)

        arguments = ['channel1', 'channel2', '--comment', 'enable channel test']
        handle_enable_channel(self.options, self.session, arguments)
        self.activate_session_mock.assert_called_once()
        self.assertEqual(2, self.session.multicall.call_count)
        self.assert_console_message(stdout, '')

    def test_handle_enable_host_no_argument(self):
        """Test enable-channel function without arguments"""
        self.session.getChannel.return_value = None
        self.session.multicall.return_value = [[None]]
        self.session.enableChannel.return_value = True

        expected = self.format_error_message("At least one channel must be specified")
        self.assert_system_exit(
            handle_enable_channel,
            self.options,
            self.session,
            [],
            stderr=expected,
            activate_session=None)

        self.activate_session_mock.assert_not_called()
        self.session.getChannel.assert_not_called()
        self.session.multicall.assert_not_called()
        self.session.enableChannel.assert_not_called()

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
