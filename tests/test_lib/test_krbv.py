from __future__ import absolute_import

import base64
# This is python-mock, not the rpm mock tool we know and love
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

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

    # this case should work on python3, but skipped still
    @unittest.skipIf(six.PY3, "skipped on python3 since missing of python-krbV")
    @mock.patch('koji.krbV', create=True)
    @mock.patch('requests_kerberos.__version__', new='0.7.0')
    @mock.patch('koji.ClientSession._serverPrincipal')
    def test_krbv_old_requests_kerberos(self, _serverPrincipal_mock, krbV_mock):
        self.assertIsNotNone(koji.krbV)
        ctx = koji.krbV.default_context.return_value
        ctx.mk_req = mock.MagicMock()
        ac = mock.MagicMock()
        ctx.mk_req.return_value = (ac, six.b('req'))
        ac.rd_priv = mock.MagicMock(return_value='session-id session-key')
        session = koji.ClientSession('whatever')
        session._callMethod = mock.MagicMock(
            return_value=(base64.encodestring(six.b('a')), base64.encodestring(six.b('b')), [0, 1, 2, 3]))
        rv = session.krb_login(principal='any@SOMEWHERE.COM', keytab='/path/to/keytab')
        self.assertTrue(rv)
