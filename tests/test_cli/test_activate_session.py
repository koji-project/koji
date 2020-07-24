from __future__ import absolute_import
import mock
import shutil
import tempfile
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.lib import activate_session


class TestActivateSession(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.warn = mock.patch('koji_cli.lib.warn').start()
        self.error = mock.patch('koji_cli.lib.error').start()
        # self.ensure_connection = mock.patch('koji_cli.lib.warn.ensure_connection').start()

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.tempdir)

    def test_activate_session_noauth(self):
        session = mock.MagicMock()
        session.logged_in = False
        options = {'authtype': 'noauth', 'debug': False}
        activate_session(session, options)
        options = {'authtype': None, 'noauth': True, 'debug': False}
        activate_session(session, options)
        session.login.assert_not_called()
        session.ssl_login.assert_not_called()
        session.gssapi_login.assert_not_called()

    def test_activate_session_ssl(self):
        session = mock.MagicMock()
        session.logged_in = True
        certfile = '%s/CERT' % self.tempdir
        options = {'authtype': 'ssl',
                'debug': False,
                'cert': certfile,
                'serverca': 'SERVERCA'}
        activate_session(session, options)
        session.ssl_login.assert_called_once_with(certfile, None, 'SERVERCA',
                    proxyuser=None)
        session.login.assert_not_called()
        session.gssapi_login.assert_not_called()

    def test_activate_session_ssl_implicit(self):
        session = mock.MagicMock()
        session.logged_in = True
        certfile = '%s/CERT' % self.tempdir
        open(certfile, 'w').close()
        options = {'authtype': None,
                'debug': False,
                'cert': certfile,
                'serverca': 'SERVERCA'}
        activate_session(session, options)
        session.ssl_login.assert_called_once_with(certfile, None, 'SERVERCA',
                    proxyuser=None)
        session.login.assert_not_called()
        session.gssapi_login.assert_not_called()

    def test_activate_session_pw(self):
        session = mock.MagicMock()
        session.logged_in = True
        options = {'authtype': 'password', 'debug': False, 'cert': ''}
        activate_session(session, options)
        session.login.assert_called_once_with()
        session.ssl_login.assert_not_called()
        session.gssapi_login.assert_not_called()

    def test_activate_session_pw_implicit(self):
        session = mock.MagicMock()
        session.logged_in = True
        options = {'authtype': None, 'debug': False, 'cert': '',
                    'user': 'USER'}
        activate_session(session, options)
        session.login.assert_called_once_with()
        session.ssl_login.assert_not_called()
        session.gssapi_login.assert_not_called()

    def test_activate_session_krb(self):
        session = mock.MagicMock()
        session.logged_in = True
        options = {'authtype': 'kerberos', 'debug': False, 'cert': '',
                'keytab': None, 'principal': None}
        activate_session(session, options)
        session.login.assert_not_called()
        session.ssl_login.assert_not_called()
        session.gssapi_login.assert_called_once_with(proxyuser=None)

    def test_activate_session_krb_implicit(self):
        session = mock.MagicMock()
        session.logged_in = True
        options = {'authtype': None, 'debug': False, 'cert': '',
                'keytab': None, 'principal': None}
        activate_session(session, options)
        session.login.assert_not_called()
        session.ssl_login.assert_not_called()
        session.gssapi_login.assert_called_once_with(proxyuser=None)

    def test_activate_session_krb_keytab(self):
        session = mock.MagicMock()
        session.logged_in = True
        options = {'authtype': 'kerberos', 'debug': False, 'cert': '',
                'keytab': 'KEYTAB', 'principal': 'PRINCIPAL'}
        activate_session(session, options)
        session.login.assert_not_called()
        session.ssl_login.assert_not_called()
        session.gssapi_login.assert_called_once_with(principal='PRINCIPAL',
                    keytab='KEYTAB', proxyuser=None)

    def test_activate_session_no_method(self):
        session = mock.MagicMock()
        session.logged_in = False
        options = {'authtype': None, 'debug': False, 'cert': ''}
        activate_session(session, options)
        session.login.assert_not_called()
        session.ssl_login.assert_not_called()
        session.gssapi_login.assert_called_once()
        self.error.assert_called_once()
