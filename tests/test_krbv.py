import unittest

# This is python-mock, not the rpm mock tool we know and love
import mock

import koji


class KrbVTestCase(unittest.TestCase):

    @mock.patch('koji.krbV', new=None)
    @mock.patch('koji.ClientSession._setup_connection')
    def test_krbv_disabled(self, krbV):
        """ Test that when krbV is absent, we behave rationally. """
        self.assertEquals(koji.krbV, None)
        session = koji.ClientSession('whatever')
        with self.assertRaises(ImportError):
            session.krb_login()
