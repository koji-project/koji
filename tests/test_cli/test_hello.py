# coding=utf-8
from __future__ import absolute_import
import mock
import six
import unittest

import koji
from koji_cli.commands import handle_moshimoshi, _printable_unicode
from . import utils


class TestPrintUnicode(utils.CliTestCase):

    greetings = (u'céad míle fáilte',
                 u'hylô',
                 u'你好',
                 u'こんにちは',
                 u'안녕하세요')

    def test_printable_unicode(self):
        for s in self.greetings:
            # make sure the type is unicode before convert in python2
            if six.PY2:
                self.assertEqual(type(s), type(unicode()))
            result = _printable_unicode(s)
            self.assertEqual(type(result), type(str()))


class TestHello(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.quiet = False
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s moshimoshi [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.huburl = "https://%s.local/%shub" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands._printable_unicode')
    def test_handle_moshimoshi(self, print_unicode_mock, stdout):
        """Test handle_moshimoshi function"""
        user = {'name': self.progname,
                'krb_principal': '%s@localhost' % self.progname}
        cert = '/etc/pki/user.cert'
        session = mock.MagicMock(baseurl=self.huburl, authtype=None)
        # Mock out the xmlrpc server
        session.getLoggedInUser.return_value = None
        session.krb_principal = user['krb_principal']
        mock_hub_version = '1.35.0'
        session.hub_version_str = mock_hub_version
        print_unicode_mock.return_value = "Hello"

        self.assert_system_exit(
            handle_moshimoshi,
            self.options, session, ['argument'],
            stderr=self.format_error_message('This command takes no arguments'),
            activate_session=None,
            exit_code=2)
        self.activate_session_mock.assert_not_called()
        session.getLoggedInUser.assert_not_called()

        # annonymous user
        message = "Not authenticated\n" + "Hello, anonymous user!"
        hubinfo = "You are using the hub at %s (Koji %s)" % (self.huburl, mock_hub_version)
        handle_moshimoshi(self.options, session, [])
        self.assert_console_message(stdout, "{0}\n\n{1}\n".format(message, hubinfo))
        self.activate_session_mock.assert_called_once_with(session, self.options)
        session.getLoggedInUser.assert_called_once_with()
        self.activate_session_mock.reset_mock()
        session.getLoggedInUser.reset_mock()

        # valid authentication
        auth_tests = {
            koji.AUTHTYPES['NORMAL']: 'Authenticated via password',
            koji.AUTHTYPES['GSSAPI']: 'Authenticated via GSSAPI',
            koji.AUTHTYPES['KERBEROS']: 'Authenticated via Kerberos principal %s' %
                                        user['krb_principal'],
            koji.AUTHTYPES['SSL']: 'Authenticated via client certificate %s' % cert
        }
        # same hubinfo
        session.getLoggedInUser.return_value = user
        message = "Hello, %s!" % self.progname
        self.options.cert = cert
        for authtype, authinfo in auth_tests.items():
            session.authtype = authtype
            print_unicode_mock.reset_mock()
            print_unicode_mock.return_value = "Hello"
            handle_moshimoshi(self.options, session, [])
            print_unicode_mock.assert_called_once()
            self.assert_console_message(
                stdout, "{0}\n\n{1}\n{2}\n".format(message, hubinfo, authinfo))
        mock_call_activate = mock.call(session, self.options)
        self.activate_session_mock.assert_has_calls([mock_call_activate, mock_call_activate,
                                                     mock_call_activate, mock_call_activate])
        session.getLoggedInUser.assert_has_calls([mock.call(), mock.call(), mock.call(),
                                                  mock.call()])

    def test_handle_moshimoshi_help(self):
        self.assert_help(
            handle_moshimoshi,
            """Usage: %s moshimoshi [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
