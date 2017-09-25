from __future__ import absolute_import
import unittest
import optparse

import koji

NORMAL_VAL = {'user': 'jdoe',
              'password': 'fakepwd',
              'krbservice': 'fakekrbservice',
              'debug_xmlrpc': True,
              'debug': False,
              'max_retries': 3,
              'retry_interval': 10,
              'offline_retry': True,
              'offline_retry_interval': 300,
              'anon_retry': True,
              'keepalive': False,
              'timeout': 30000,
              'use_fast_upload': False,
              'upload_blocksize': 1024,
              'krb_rdns': 'fakerdns',
              'krb_canon_host': 'fakehost',
              'no_ssl_verify': True,
              'serverca': '/fake/serverca.cert',
              }

EMPTY_VAL = {}

NONE_VAL = {'user': None,
            'password': None,
            'krbservice': None,
            'debug_xmlrpc': None,
            'debug': None,
            'max_retries': None,
            'retry_interval': None,
            'offline_retry': None,
            'offline_retry_interval': None,
            'anon_retry': None,
            'keepalive': None,
            'timeout': None,
            'use_fast_upload': None,
            'upload_blocksize': None,
            'krb_rdns': None,
            'krb_canon_host': None,
            'no_ssl_verify': None,
            'serverca': None,
            }

MEANINGLESS_VAL = {'somekey': 'somevalue'}

MIXED_VAL = {'user': None,
             'password': None,
             'anon_retry': 3,
             'keepalive': True,
             'timeout': 100,
             'krb_rdns': 'fakerdns',
             'meaningless': 'wow',
             'nonval': None}

MIXED_REL = {'anon_retry': 3,
             'keepalive': True,
             'timeout': 100,
             'krb_rdns': 'fakerdns',
             }


class TestGrabSessionOptions(unittest.TestCase):
    """TestCase for grab_session_options"""

    def test_optparse_value(self):
        rel = koji.grab_session_options(optparse.Values(NORMAL_VAL))
        self.assertEqual(rel, NORMAL_VAL)
        rel = koji.grab_session_options(optparse.Values(EMPTY_VAL))
        self.assertEqual(rel, EMPTY_VAL)
        rel = koji.grab_session_options(optparse.Values(NONE_VAL))
        self.assertEqual(rel, {})
        rel = koji.grab_session_options(optparse.Values(MEANINGLESS_VAL))
        self.assertEqual(rel, {})
        rel = koji.grab_session_options(optparse.Values(MIXED_VAL))
        self.assertEqual(rel, MIXED_REL)

    def test_dict(self):
        rel = koji.grab_session_options(NORMAL_VAL)
        self.assertEqual(rel, NORMAL_VAL)
        rel = koji.grab_session_options(EMPTY_VAL)
        self.assertEqual(rel, EMPTY_VAL)
        rel = koji.grab_session_options(NONE_VAL)
        self.assertEqual(rel, {})
        rel = koji.grab_session_options(MEANINGLESS_VAL)
        self.assertEqual(rel, {})
        rel = koji.grab_session_options(MIXED_VAL)
        self.assertEqual(rel, MIXED_REL)
