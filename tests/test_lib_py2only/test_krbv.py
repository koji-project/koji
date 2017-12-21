from __future__ import absolute_import

import unittest

# This is python-mock, not the rpm mock tool we know and love
import mock

import koji


class KrbVTestCase(unittest.TestCase):
    @mock.patch('koji.krbV', new=None)
    @mock.patch('koji.requests_kerberos', new=None)
    def test_krbv_disabled(self):
        """Test that when krbV and gssapi are absent, we behave rationally"""
        self.assertEquals(koji.krbV, None)
        session = koji.ClientSession('whatever')
        with self.assertRaises(ImportError):
            session.krb_login()

    @mock.patch('koji.krbV', autospec=True)
    @mock.patch('requests_kerberos.__version__', new='0.7.0')
    def test_krbv_old_requests_kerberos(self, krbV_mock):
        """Test that when krbV and gssapi are absent, we behave rationally"""
        self.assertIsNotNone(koji.krbV)
        session = koji.ClientSession('whatever')
        with self.assertRaises(koji.AuthError) as cm:
            session.krb_login(principal='any@somewhere.com')
        self.assertEqual(cm.exception.args[0], 'cannot specify a principal without a keytab')
