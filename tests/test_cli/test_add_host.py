from __future__ import absolute_import

import mock
import six

import koji
from koji_cli.commands import handle_add_host
from . import utils


class TestAddHost(utils.CliTestCase):

    def setUp(self):
        self.maxDiff = None
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s add-host [options] <hostname> <arch> [<arch> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_add_host(self, stdout):
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
        self.activate_session_mock.assert_called_once_with(session, options)
        session.getHost.assert_called_once_with(host)
        session.addHost.assert_called_once_with(host, arches, **kwargs)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_add_host_no_krb_principal(self, stdout):
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
        self.activate_session_mock.assert_called_once_with(session, options)
        session.getHost.assert_called_once_with(host)
        session.addHost.assert_called_once_with(host, arches, force=False)
        self.assertNotEqual(rv, 1)

    def test_handle_add_host_dupl(self):
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
        self.assert_system_exit(
            handle_add_host,
            options, session, arguments,
            stdout='',
            stderr='host is already in the database\n',
            exit_code=1,
            activate_session=None)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(session, options)
        session.getHost.assert_called_once_with(host)
        session.addHost.assert_not_called()

    def test_handle_add_host_without_args(self):
        arguments = []
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        self.assert_system_exit(
            handle_add_host,
            options, session, arguments,
            stdout='',
            stderr=self.format_error_message('Please specify a hostname and at least one arch'),
            exit_code=2,
            activate_session=None)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        session.hasHost.assert_not_called()
        session.addHost.assert_not_called()

    def test_handle_add_host_help(self):
        self.assert_help(
            handle_add_host,
            """Usage: %s add-host [options] <hostname> <arch> [<arch> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --krb-principal=KRB_PRINCIPAL
                        set a non-default kerberos principal for the host
  --force               if existing used is a regular user, convert it to a
                        host
""" % self.progname)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    def test_handle_add_host_failed(self, stderr):
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
        with self.assertRaises(koji.GenericError):
            handle_add_host(options, session, arguments)
        actual = stderr.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(session, options)
        session.getHost.assert_called_once_with(host)
        session.addHost.assert_called_once_with(host, arches, **kwargs)
