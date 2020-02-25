from __future__ import absolute_import
import json
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_call
from . import utils


class TestCall(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s call [options] <name> [<arg> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_call(self, activate_session_mock, stdout):
        """Test handle_call function"""
        arguments = ['ssl_login', 'cert=/etc/pki/cert', 'debug']
        response = "SUCCESS"
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.ssl_login.return_value = response

        handle_call(options, session, arguments)
        activate_session_mock.assert_called_with(session, options)
        session.ssl_login.assert_called_with('debug', cert='/etc/pki/cert')
        self.assert_console_message(stdout, "'%s'\n" % response)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_call_python_syntax(self, activate_session_mock, stdout):
        """Test handle_call with python syntax"""
        arguments = []
        response = ["SUCCESS", "FAKE-RESPONSE"]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.ssl_login.return_value = response[1]

        # Invalid python syntax
        arguments = ['ssl_login', 'cert=/etc/pki/cert', '--python']
        with self.assertRaises(SyntaxError, msg='invalid syntax'):
            handle_call(options, session, arguments)

        arguments = ['ssl_login', '--kwargs', '{"cert":"/etc/pki/cert"}']
        handle_call(options, session, arguments)
        activate_session_mock.assert_called_with(session, options)
        session.ssl_login.assert_called_with(cert='/etc/pki/cert')
        self.assert_console_message(stdout, "'%s'\n" % response[1])

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_call_json_output(self, activate_session_mock, stdout):
        """Test handle_call with json output"""
        arguments = ['ssl_login', 'cert=/etc/pki/cert', '--json-output']
        options = mock.MagicMock()

        response = {
            'method': 'ssl_login',
            'parameters': {
                'cert': '/etc/pki/cert',
                'ca': ['/etc/pki/clientca', '/etc/pki/serverca'],
            },
            'result': 'success'
        }

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.ssl_login.return_value = response

        handle_call(options, session, arguments)
        activate_session_mock.assert_called_with(session, options)
        session.ssl_login.assert_called_with(cert='/etc/pki/cert')

        expect = json.dumps(response, indent=2, separators=(',', ': '))
        self.assert_console_message(stdout, '%s\n' % expect)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_call_errors(self, activate_session_mock, stderr):
        """Test handle_call error messages"""
        arguments = []
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        # argument is empty
        expected = self.format_error_message(
                    "Please specify the name of the XML-RPC method")
        self.assert_system_exit(
            handle_call,
            options,
            session,
            arguments,
            stderr=expected,
            activate_session=None)
        activate_session_mock.assert_not_called()

        arguments = ['ssl_login', '--python', '--json-output']

        module = {
            'ast': "The ast module is required to read python syntax",
            'json': "The json module is required to output JSON syntax",
        }

        for mod, msg in module.items():
            with mock.patch('koji_cli.commands.%s' % mod, new=None):
                with self.assertRaises(SystemExit) as ex:
                    handle_call(options, session, arguments)
                self.assertExitCode(ex, 2)
            expected = self.format_error_message(msg)
            self.assert_console_message(stderr, expected)
            activate_session_mock.assert_not_called()

    def test_handle_call_help(self):
        """Test handle_call help message"""
        self.assert_help(
            handle_call,
            """Usage: %s call [options] <name> [<arg> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help       show this help message and exit
  --python         Use python syntax for values
  --kwargs=KWARGS  Specify keyword arguments as a dictionary (implies
                   --python)
  --json-output    Use JSON syntax for output
""" % (self.progname))


if __name__ == '__main__':
    unittest.main()
