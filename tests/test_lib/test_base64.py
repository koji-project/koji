# coding=utf-8
from __future__ import absolute_import
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji.util import base64encode


class Base64EncodeTestCase(unittest.TestCase):

    DATA = [
            # list of pairs [string, encoded_string]
            [b'Hello World', 'SGVsbG8gV29ybGQ='],
            [b'BZh91AY&SY\x14\x99\\\xcf\x05y\r\x7f\xff\xff',
                'QlpoOTFBWSZTWRSZXM8FeQ1///8=']
            ]

    def test_base64encode(self):
        for s, expected in self.DATA:
            result = base64encode(s)
            self.assertEqual(result, expected)
            if six.PY3:
                result = base64encode(s, as_bytes=True)
                self.assertEqual(result, expected.encode('ascii'))
