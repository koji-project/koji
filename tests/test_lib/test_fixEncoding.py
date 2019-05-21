#!/usr/bin/python2
# coding=utf-8

"""Test the __init__.py module"""

from __future__ import absolute_import
import koji
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest


class FixEncodingTestCase(unittest.TestCase):
    """Main test case container"""

    simple_values = [
        # [ unicode value, utf-8 encoded string ]
        ['', ''],
        [u'', ''],
        [u'góðan daginn', 'g\xc3\xb3\xc3\xb0an daginn'],
        [u'hej', 'hej'],
        [u'zdravstvuite', 'zdravstvuite'],
        [u'céad míle fáilte', 'c\xc3\xa9ad m\xc3\xadle f\xc3\xa1ilte'],
        [u'dobrý den', 'dobr\xc3\xbd den'],
        [u'hylô', 'hyl\xc3\xb4'],
        [u'jó napot', 'j\xc3\xb3 napot'],
        [u'tervehdys', 'tervehdys'],
        [u'olá', 'ol\xc3\xa1'],
        [u'grüezi', 'gr\xc3\xbcezi'],
        [u'dobre dan', 'dobre dan'],
        [u'hello', 'hello'],
        [u'bună ziua', 'bun\xc4\x83 ziua'],
        [u'こんにちは', '\xe3\x81\x93\xe3\x82\x93\xe3\x81\xab\xe3\x81\xa1\xe3\x81\xaf'],
        [u'你好', '\xe4\xbd\xa0\xe5\xa5\xbd'],
        [u'नमस्कार',  '\xe0\xa4\xa8\xe0\xa4\xae\xe0\xa4\xb8\xe0\xa5\x8d\xe0\xa4\x95\xe0\xa4\xbe\xe0\xa4\xb0'],
        [u'안녕하세요', '\xec\x95\x88\xeb\x85\x95\xed\x95\x98\xec\x84\xb8\xec\x9a\x94'],
    ]

    def test_fixEncoding(self):
        """Test the fixEncoding function"""
        for a, b in self.simple_values:
            self.assertEqual(koji.fixEncoding(b), b)
            if six.PY2:
                self.assertEqual(koji.fixEncoding(a), b)
                c = a.encode('utf16')
                self.assertEqual(koji.fixEncoding(c, fallback='utf16'), b)
                d = a[:-3] + u'\x00\x01' + a[-3:]
                self.assertEqual(koji.fixEncoding(d, remove_nonprintable=True), b)
            else:
                self.assertEqual(koji.fixEncoding(a), a)
                d = a[:-3] + u'\x00\x01' + a[-3:]
                self.assertEqual(koji.fixEncoding(d, remove_nonprintable=True), a)

    def test_fix_print(self):
        """Test the _fix_print function"""
        actual, expected = [], []
        for a, b in self.simple_values:
            actual.append(koji._fix_print(b))
            expected.append(b)
        expected = '\n'.join(expected)
        actual = '\n'.join(actual)
        self.assertEqual(actual, expected)

    complex_values = [
        # [ value, fixed ]
        [{}, {}],
        [(), ()],
        [None, None],
        [[], []],
        [{u'a': 'a' , 'b' : {'c': u'c\x00'}},
         {'a': 'a' , 'b' : {'c':  'c\x00'}}],
        # iso8859-15 fallback
        ['g\xf3\xf0an daginn', 'g\xc3\xb3\xc3\xb0an daginn'],
    ]

    nonprint = [
        ['hello\0world\0', 'helloworld'],
        [u'hello\0world\0', 'helloworld'],
        [[u'hello\0world\0'], ['helloworld']],
        [{0: u'hello\0world\0'}, {0: 'helloworld'}],
        [[{0: u'hello\0world\0'}], [{0: 'helloworld'}]],
    ]

    def test_fixEncodingRecurse(self):
        """Test the fixEncodingRecurse function"""
        if six.PY3:
            # don't test for py3
            return
        for a, b in self.simple_values:
            self.assertEqual(koji.fixEncoding(a), b)
        for a, b in self.complex_values:
            self.assertEqual(koji.fixEncodingRecurse(a), b)
        for a, b in self.nonprint:
            self.assertEqual(koji.fixEncodingRecurse(a, remove_nonprintable=True), b)


if __name__ == '__main__':
    unittest.main()
