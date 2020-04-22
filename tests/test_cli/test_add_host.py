from __future__ import absolute_import
import mock
import os
import six
import sys

import koji
from koji_cli.commands import handle_add_host
from . import utils

class TestAddHost(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_host(self, activate_session_mock, stdout):
        host = 'host'
        host_id = 1
        arches = ['arch1', 'arch2']
        krb_principal = '--krb-principal=krb'
        arguments = [host] + arches
        arguments.append(krb_principal)
        kwargs = {'krb_principal': 'krb', 'force': False}
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getHost.return_value = None
        session.addHost.return_value = host_id
        # Run it and check immediate output
        # args: host, arch1, arch2, --krb-principal=krb
        # expected: success
        rv = handle_add_host(options, session, arguments)
        actual = stdout.getvalue()
        expected = 'host added: id 1\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.getHost.assert_called_once_with(host)
        session.addHost.assert_called_once_with(host, arches, **kwargs)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_host_no_krb_principal(
            self, activate_session_mock, stdout):
        host = 'host'
        host_id = 1
        arches = ['arch1', 'arch2']
        arguments = [host] + arches
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.getHost.return_value = None
        session.addHost.return_value = host_id
        # Run it and check immediate output
        # args: host, arch1, arch2
        # expected: success
        rv = handle_add_host(options, session, arguments)
        actual = stdout.getvalue()
        expected = 'host added: id 1\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.getHost.assert_called_once_with(host)
        session.addHost.assert_called_once_with(host, arches, force=False)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_host_dupl(self, activate_session_mock, stderr):
        host = 'host'
        host_id = 1
        arches = ['arch1', 'arch2']
        krb_principal = '--krb-principal=krb'
        arguments = [host] + arches
        arguments.append(krb_principal)
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.getHost.return_value = host_id
        # Run it and check immediate output
        # args: host, arch1, arch2, --krb-principal=krb
        # expected: failed, host already exists
        with self.assertRaises(SystemExit) as ex:
            handle_add_host(options, session, arguments)
        self.assertExitCode(ex, 1)
        actual = stderr.getvalue()
        expected = 'host is already in the database\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.getHost.assert_called_once_with(host)
        session.addHost.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_host_help(self, activate_session_mock, stderr, stdout):
        arguments = []
        options = mock.MagicMock()
        progname = os.path.basename(sys.argv[0]) or 'koji'

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            handle_add_host(options, session, arguments)
        self.assertExitCode(ex, 2)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = ''
        expected_stderr = """Usage: %s add-host [options] <hostname> <arch> [<arch> ...]
(Specify the --help global option for a list of other help options)

%s: error: Please specify a hostname and at least one arch
""" % (progname, progname)
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        session.hasHost.assert_not_called()
        session.addHost.assert_not_called()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_host_failed(self, activate_session_mock, stderr):
        host = 'host'
        arches = ['arch1', 'arch2']
        krb_principal = '--krb-principal=krb'
        arguments = [host] + arches
        arguments.append(krb_principal)
        kwargs = {'krb_principal': 'krb', 'force': False}
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        session.getHost.return_value = None
        session.addHost.side_effect = koji.GenericError
        # Run it and check immediate output
        # args: host, arch1, arch2, --krb-principal=krb
        # expected: failed
        with self.assertRaises(koji.GenericError) as ex:
            handle_add_host(options, session, arguments)
        actual = stderr.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.getHost.assert_called_once_with(host)
        session.addHost.assert_called_once_with(host, arches, **kwargs)
