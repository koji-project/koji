from __future__ import absolute_import
import mock
import os
import unittest

import koji


class TestGSSAPI(unittest.TestCase):

    def setUp(self):
        self.session = koji.ClientSession('https://koji.example.com/kojihub', {})
        self.session._callMethod = mock.MagicMock(name='_callMethod')

    def tearDown(self):
        mock.patch.stopall()

    maxDiff = None

    @mock.patch('koji.HTTPKerberosAuth', new=None)
    def test_gssapi_disabled(self):
        with self.assertRaises(ImportError):
            self.session.gssapi_login()

    def test_gssapi_login(self):
        old_environ = dict(**os.environ)
        self.session.gssapi_login()
        self.session._callMethod.assert_called_once_with('sslLogin', [None],
                retry=False)
        self.assertEqual(old_environ, dict(**os.environ))

    def test_gssapi_login_keytab(self):
        principal = 'user@EXAMPLE.COM'
        keytab = '/path/to/keytab'
        ccache = '/path/to/cache'
        old_environ = dict(**os.environ)
        self.session.gssapi_login(principal, keytab, ccache)
        self.session._callMethod.assert_called_once_with('sslLogin', [None],
                retry=False)
        self.assertEqual(old_environ, dict(**os.environ))

    def test_gssapi_login_error(self):
        old_environ = dict(**os.environ)
        self.session._callMethod.side_effect = Exception('login failed')
        with self.assertRaises(koji.AuthError):
            self.session.gssapi_login()
        self.session._callMethod.assert_called_once_with('sslLogin', [None],
                retry=False)
        self.assertEqual(old_environ, dict(**os.environ))

    def test_gssapi_login_http(self):
        old_environ = dict(**os.environ)
        url1 = 'http://koji.example.com/kojihub'
        url2 = 'https://koji.example.com/kojihub'

        # successful gssapi auth should force https
        self.session.baseurl = url1
        self.session.gssapi_login()
        self.assertEqual(self.session.baseurl, url2)

        # failed gssapi auth should leave the url alone
        self.session.baseurl = url1
        self.session._callMethod.side_effect = Exception('login failed')
        with self.assertRaises(koji.AuthError):
            self.session.gssapi_login()
        self.assertEqual(self.session.baseurl, url1)
        self.assertEqual(old_environ, dict(**os.environ))
