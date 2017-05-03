from __future__ import absolute_import
import unittest

# This is python-mock, not the rpm mock tool we know and love
import mock

import koji


class KrbVTestCase(unittest.TestCase):

    @mock.patch('koji.krbV', new=None)
    def test_krbv_disabled(self):
        """ Test that when krbV is absent, we behave rationally. """
        self.assertEquals(koji.krbV, None)
        session = koji.ClientSession('whatever')
        with self.assertRaises(ImportError):
            session.krb_login()
