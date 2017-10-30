from __future__ import absolute_import
import mock
import os
import six
import sys
import unittest
import koji

from koji_cli.commands import handle_moshimoshi


class TestHello(unittest.TestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.progname = os.path.basename(sys.argv[0]) or 'koji'
        self.huburl = "https://%s.local/%shub" % (self.progname, self.progname)

    def assert_console_output(self, device, expected, wipe=True, regex=False):
        if not isinstance(device, six.StringIO):
            raise TypeError('Not a StringIO object')

        output = device.getvalue()
        if not regex:
            self.assertMultiLineEqual(output, expected)
        else:
            six.assertRegex(self, output, expected)
        if wipe:
            device.truncate(0)
            device.seek(0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands._printable_unicode')
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_moshimoshi(
            self,
            activate_session_mock,
            print_unicode_mock,
            stderr,
            stdout):
        """Test handle_moshimoshi function"""
        user = {'name': self.progname,
                'krb_principal': '%s@localhost' % self.progname}
        cert = '/etc/pki/user.cert'
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock(baseurl=self.huburl, authtype=None)
        session.getLoggedInUser.return_value = None
        print_unicode_mock.return_value = "Hello"

        with self.assertRaises(SystemExit) as cm:
            handle_moshimoshi(options, session, ['argument'])
        expect = """Usage: %s moshimoshi [options]

%s: error: This command takes no arguments
""" % (self.progname, self.progname)
        self.assert_console_output(stderr, expect)
        self.assertEqual(cm.exception.code, 2)

        auth_tests = {
            koji.AUTHTYPE_NORMAL: 'Authenticated via password',
            koji.AUTHTYPE_GSSAPI: 'Authenticated via GSSAPI',
            koji.AUTHTYPE_KERB: 'Authenticated via Kerberos principal %s' %
                                user['krb_principal'],
            koji.AUTHTYPE_SSL: 'Authenticated via client certificate %s' %
                                cert
        }

        message = "Not authenticated\n" + "Hello, anonymous user!"
        hubinfo = "You are using the hub at %s" % self.huburl
        handle_moshimoshi(options, session, [])
        self.assert_console_output(
            stdout, "{0}\n\n{1}\n".format(message, hubinfo))

        session.getLoggedInUser.return_value = user
        message = "Hello, %s!" % self.progname
        options.cert = cert
        for authtype, authinfo in auth_tests.items():
            session.authtype = authtype
            print_unicode_mock.reset_mock()
            print_unicode_mock.return_value = "Hello"
            handle_moshimoshi(options, session, [])
            print_unicode_mock.assert_called_once()
            self.assert_console_output(
                stdout, "{0}\n\n{1}\n{2}\n".format(message, hubinfo, authinfo))

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_moshimoshi_help(
            self, activate_session_mock, stderr, stdout):
        """Test  handle_moshimoshi help message full output"""
        arguments = ['--help']
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as cm:
            handle_moshimoshi(options, session, arguments)
        expected_stdout = """Usage: %s moshimoshi [options]

Options:
  -h, --help  show this help message and exit
""" % (self.progname)
        self.assert_console_output(stdout, expected_stdout)
        self.assert_console_output(stderr, '')

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        self.assertEqual(cm.exception.code, 0)

if __name__ == '__main__':
    unittest.main()
