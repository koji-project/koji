from __future__ import absolute_import
import json
try:
    from unittest import mock
except ImportError:
    import mock
import six
import unittest
import koji

from koji_cli.commands import handle_call
from . import utils


class TestCall(utils.CliTestCase):

    def setUp(self):
        # Show long diffs in error output...
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.quiet = True
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s call [options] <name> [<arg> ...]

<arg> values of the form NAME=VALUE are treated as keyword arguments
Note, that you can use global option --noauth for anonymous calls here
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_call(self, stdout):
        """Test handle_call function"""
        arguments = ['ssl_login', 'cert=/etc/pki/cert', 'debug']
        response = "SUCCESS"
        self.session.ssl_login.return_value = response

        handle_call(self.options, self.session, arguments)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.ssl_login.assert_called_with('debug', cert='/etc/pki/cert')
        self.assert_console_message(stdout, "'%s'\n" % response)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_call_python_syntax(self, stdout):
        """Test handle_call with python syntax"""
        response = ["SUCCESS", "FAKE-RESPONSE"]
        self.session.ssl_login.return_value = response[1]

        # Invalid python syntax
        arguments = ['ssl_login', 'cert=/etc/pki/cert', '--python']
        with self.assertRaises(SyntaxError, msg='invalid syntax'):
            handle_call(self.options, self.session, arguments)

        arguments = ['ssl_login', '--kwargs', '{"cert":"/etc/pki/cert"}']
        handle_call(self.options, self.session, arguments)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.ssl_login.assert_called_with(cert='/etc/pki/cert')
        self.assert_console_message(stdout, "'%s'\n" % response[1])

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_call_json_syntax(self, stdout):
        """Test handle_call with json input syntax"""
        response = ["SUCCESS", "FAKE-RESPONSE"]
        self.session.ssl_login.return_value = response[1]

        # Invalid json syntax
        arguments = ['--json-input', 'ssl_login', 'cert=/etc/pki/cert']
        self.assert_system_exit(
            handle_call,
            self.options, self.session, arguments,
            stderr=self.format_error_message("Invalid value: '/etc/pki/cert'"),
            activate_session=None)
        self.activate_session_mock.assert_not_called()

        # Incompatible opts
        arguments = ['--json', '--python', 'ssl_login', 'cert=/etc/pki/cert']
        self.assert_system_exit(
            handle_call,
            self.options, self.session, arguments,
            stderr=self.format_error_message("The --python option conflicts with using --json-input"),
            activate_session=None)
        self.activate_session_mock.assert_not_called()

        arguments = ['--json-input', 'ssl_login', '--kwargs', '{"cert":"/etc/pki/cert"}']
        handle_call(self.options, self.session, arguments)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.ssl_login.assert_called_with(cert='/etc/pki/cert')
        self.assert_console_message(stdout, "'%s'\n" % response[1])

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_call_bare_strings(self, stdout):
        """Test handle_call with bare string fallback"""
        response = ["SUCCESS", "FAKE-RESPONSE"]
        self.session.ssl_login.return_value = response[1]

        # Invalid json syntax, but with bare-string fallback
        arguments = ['--json-input', '--bare-strings', 'ssl_login', 'cert=/etc/pki/cert']
        handle_call(self.options, self.session, arguments)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.ssl_login.assert_called_with(cert='/etc/pki/cert')
        self.assert_console_message(stdout, "'%s'\n" % response[1])

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_call_json_output(self, stdout):
        """Test handle_call with json output"""
        arguments = ['ssl_login', 'cert=/etc/pki/cert', '--json-output']

        response = {
            'method': 'ssl_login',
            'parameters': {
                'cert': '/etc/pki/cert',
            },
            'result': 'success'
        }

        self.session.ssl_login.return_value = response

        handle_call(self.options, self.session, arguments)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.ssl_login.assert_called_with(cert='/etc/pki/cert')

        expect = json.dumps(response, indent=2, separators=(',', ': '))
        self.assert_console_message(stdout, '%s\n' % expect)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    def test_handle_call_errors(self, stderr):
        """Test handle_call error messages"""
        arguments = []

        # Run it and check immediate output
        # argument is empty
        self.assert_system_exit(
            handle_call,
            self.options, self.session, arguments,
            stderr=self.format_error_message("Please specify the name of the XML-RPC method"),
            activate_session=None)
        self.activate_session_mock.assert_not_called()

        arguments = ['ssl_login', '--python', '--json-output']

        module = {
            'ast': "The ast module is required to read python syntax",
            'json': "The json module is required to use JSON syntax",
        }

        for mod, msg in module.items():
            with mock.patch('koji_cli.commands.%s' % mod, new=None):
                with self.assertRaises(SystemExit) as ex:
                    handle_call(self.options, self.session, arguments)
                self.assertExitCode(ex, 2)
            expected = self.format_error_message(msg)
            self.assert_console_message(stderr, expected)
            self.activate_session_mock.assert_not_called()

    def test_handle_call_help(self):
        """Test handle_call help message"""
        self.assert_help(
            handle_call,
            """Usage: %s call [options] <name> [<arg> ...]

<arg> values of the form NAME=VALUE are treated as keyword arguments
Note, that you can use global option --noauth for anonymous calls here
(Specify the --help global option for a list of other help options)

Options:
  -h, --help          show this help message and exit
  -p, --python        Use python syntax for RPC parameter values
  --kwargs=KWARGS     Specify keyword arguments as a dictionary (implies
                      --python or --json-input)
  -j, --json          Use JSON syntax for input and output
  --json-input        Use JSON syntax for input
  --json-output       Use JSON syntax for output
  -b, --bare-strings  Treat invalid json/python as bare strings
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
