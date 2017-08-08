from __future__ import absolute_import
import unittest

# This is python-mock, not the rpm mock tool we know and love
import mock

import koji


class KrbVTestCase(unittest.TestCase):

    @mock.patch('koji.krbV', new=None)
    @mock.patch('koji.HTTPKerberosAuth', new=None)
    def test_krbv_disabled(self):
        """Test that when krbV and gssapi are absent, we behave rationally"""
        self.assertEquals(koji.krbV, None)
        session = koji.ClientSession('whatever')
        with self.assertRaises(ImportError):
            session.krb_login()
