import unittest
import mock

from koji_cli.lib import activate_session


class TestActivateSession(unittest.TestCase):

    def setUp(self):
        self.isfile = mock.patch('os.path.isfile').start()
        self.warn = mock.patch('koji_cli.lib.warn').start()
        self.error = mock.patch('koji_cli.lib.error').start()
        # self.ensure_connection = mock.patch('koji_cli.lib.warn.ensure_connection').start()
        self.has_krb_creds = mock.patch('koji_cli.lib.has_krb_creds').start()
        self.isfile.return_value = False
        self.has_krb_creds.return_value = False

    def tearDown(self):
        mock.patch.stopall()

    def test_activate_session_noauth(self):
        session = mock.MagicMock()
        session.logged_in = False
        options = {'authtype': 'noauth', 'debug': False}
        activate_session(session, options)
        options = {'authtype': None, 'noauth': True, 'debug': False}
        activate_session(session, options)
        session.login.assert_not_called()
        session.ssl_login.assert_not_called()
        session.krb_login.assert_not_called()

    def test_activate_session_ssl(self):
        session = mock.MagicMock()
        session.logged_in = True
        options = {'authtype': 'ssl',
                'debug': False,
                'cert': 'CERT',
                'serverca': 'SERVERCA'}
        activate_session(session, options)
        session.ssl_login.assert_called_once_with('CERT', None, 'SERVERCA',
                    proxyuser=None)
        session.login.assert_not_called()
        session.krb_login.assert_not_called()

    def test_activate_session_ssl_implicit(self):
        session = mock.MagicMock()
        session.logged_in = True
        options = {'authtype': None,
                'debug': False,
                'cert': 'CERT',
                'serverca': 'SERVERCA'}
        self.isfile.return_value = True
        activate_session(session, options)
        session.ssl_login.assert_called_once_with('CERT', None, 'SERVERCA',
                    proxyuser=None)
        session.login.assert_not_called()
        session.krb_login.assert_not_called()

    def test_activate_session_pw(self):
        session = mock.MagicMock()
        session.logged_in = True
        self.isfile.return_value = True
        options = {'authtype': 'password', 'debug': False, 'cert': None}
        activate_session(session, options)
        session.login.assert_called_once_with()
        session.ssl_login.assert_not_called()
        session.krb_login.assert_not_called()

    def test_activate_session_pw_implicit(self):
        session = mock.MagicMock()
        session.logged_in = True
        self.isfile.return_value = False
        options = {'authtype': None, 'debug': False, 'cert': None,
                    'user': 'USER'}
        activate_session(session, options)
        session.login.assert_called_once_with()
        session.ssl_login.assert_not_called()
        session.krb_login.assert_not_called()

    def test_activate_session_krb(self):
        session = mock.MagicMock()
        session.logged_in = True
        self.isfile.return_value = True
        options = {'authtype': 'kerberos', 'debug': False, 'cert': None,
                'keytab': None, 'principal': None}
        activate_session(session, options)
        session.login.assert_not_called()
        session.ssl_login.assert_not_called()
        session.krb_login.assert_called_once_with(proxyuser=None)

    def test_activate_session_krb_implicit(self):
        session = mock.MagicMock()
        session.logged_in = True
        self.isfile.return_value = False
        options = {'authtype': None, 'debug': False, 'cert': None,
                'keytab': None, 'principal': None}
        self.has_krb_creds.return_value = True
        activate_session(session, options)
        session.login.assert_not_called()
        session.ssl_login.assert_not_called()
        session.krb_login.assert_called_once_with(proxyuser=None)

    def test_activate_session_krb_keytab(self):
        session = mock.MagicMock()
        session.logged_in = True
        self.isfile.return_value = True
        options = {'authtype': 'kerberos', 'debug': False, 'cert': None,
                'keytab': 'KEYTAB', 'principal': 'PRINCIPAL'}
        activate_session(session, options)
        session.login.assert_not_called()
        session.ssl_login.assert_not_called()
        session.krb_login.assert_called_once_with(principal='PRINCIPAL',
                    keytab='KEYTAB', proxyuser=None)

    def test_activate_session_no_method(self):
        session = mock.MagicMock()
        session.logged_in = False
        options = {'authtype': None, 'debug': False, 'cert': None}
        self.has_krb_creds.return_value = False
        activate_session(session, options)
        session.login.assert_not_called()
        session.ssl_login.assert_not_called()
        session.krb_login.assert_not_called()
        self.error.assert_called_once()
