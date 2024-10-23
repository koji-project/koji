from __future__ import absolute_import
import unittest
try:
    from unittest import mock
    from unittest.mock import call
except ImportError:
    import mock
    from mock import call

import six

import koji
from koji_cli.commands import handle_enable_host
from . import utils


class TestEnableHost(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s enable-host [options] <hostname> [<hostname> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_enable_host_no_such_host(self):
        """Test %s function""" % handle_enable_host.__name__

        self.session.getHost.return_value = None
        self.session.enableHost.return_value = True
        self.session.editHost.return_value = True

        #
        # session.multiCall returns:
        #
        # [[{'comment': None,
        #    'capacity': 2.0,
        #    'name': 'kbuilder01',
        #    'enabled': True,
        #    'arches': 'x86_64',
        #    'task_load': 0.0,
        #    'ready': False,
        #    'user_id': 4,
        #    'id': 2, 'description': None}],
        #  [{'comment': None,
        #     'capacity': 2.0,
        #     'name': 'kbuilder02' ...}]
        #

        self.session.multiCall.return_value = [[None], [None]]

        arguments = ['host1', 'host2']
        expect = ''
        for host in arguments:
            expect += "No such host: %s\n" % host
        stderr_exp = "No changes made. Please correct the command line.\n"
        self.assert_system_exit(
            handle_enable_host,
            self.options,
            self.session,
            arguments,
            stdout=expect,
            stderr=stderr_exp,
            activate_session=None,
            exit_code=1
        )
        self.session.getHost.assert_has_calls([call('host1'), call('host2')])
        self.session.multiCall.assert_called_once()
        self.session.enableHost.assert_not_called()
        self.session.editHost.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_enable_host_valid(self, stdout):
        self.session.multiCall.return_value = [
            [{'id': 1, 'name': 'host1'}], [{'id': 2, 'name': 'host2'}]
        ]

        arguments = ['host1', 'host2', '--comment', 'disable host test']
        handle_enable_host(self.options, self.session, arguments)
        self.activate_session_mock.assert_called_once()
        self.session.getHost.assert_has_calls([call('host1'), call('host2')])
        self.assertEqual(2, self.session.multiCall.call_count)
        self.session.enableHost.assert_has_calls([call('host1'), call('host2')])
        self.session.editHost.assert_has_calls(
            [call('host1', comment='disable host test'),
             call('host2', comment='disable host test')])
        self.assert_console_message(stdout, '')

    def test_handle_enable_host_no_argument(self):
        """Test %s function without arguments""" % handle_enable_host.__name__
        self.session.getHost.return_value = None
        self.session.multiCall.return_value = [[None]]
        self.session.enableHost.return_value = True
        self.session.editHost.return_value = True

        expected = self.format_error_message("At least one host must be specified")
        self.assert_system_exit(
            handle_enable_host,
            self.options,
            self.session,
            [],
            stderr=expected,
            activate_session=None)

        self.activate_session_mock.assert_not_called()
        self.session.getHost.assert_not_called()
        self.session.multiCall.assert_not_called()
        self.session.enableHost.assert_not_called()
        self.session.editHost.assert_not_called()

    def test_handle_enable_host_help(self):
        """Test %s help message""" % handle_enable_host.__name__
        self.assert_help(
            handle_enable_host,
            """Usage: %s enable-host [options] <hostname> [<hostname> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help         show this help message and exit
  --comment=COMMENT  Comment indicating why the host(s) are being enabled
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
