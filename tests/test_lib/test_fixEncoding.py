#!/usr/bin/python
# coding=utf-8

"""Test the __init__.py module"""

from __future__ import absolute_import
import koji
import six
import unittest
import mock

class FixEncodingTestCase(unittest.TestCase):
    """Main test case container"""

    simple_values = [
        # [ value, fixed ]
        ['', six.b('')],
        [u'', six.b('')],
        [u'góðan daginn', six.b('g\xc3\xb3\xc3\xb0an daginn')],
        [u'hej', six.b('hej')],
        [u'zdravstvuite', six.b('zdravstvuite')],
        [u'céad míle fáilte', six.b('c\xc3\xa9ad m\xc3\xadle f\xc3\xa1ilte')],
        [u'dobrý den', six.b('dobr\xc3\xbd den')],
        [u'hylô', six.b('hyl\xc3\xb4')],
        [u'jó napot', six.b('j\xc3\xb3 napot')],
        [u'tervehdys', six.b('tervehdys')],
        [u'olá', six.b('ol\xc3\xa1')],
        [u'grüezi', six.b('gr\xc3\xbcezi')],
        [u'dobre dan', six.b('dobre dan')],
        [u'hello', six.b('hello')],
        [u'bună ziua', six.b('bun\xc4\x83 ziua')],
        [u'こんにちは', six.b('\xe3\x81\x93\xe3\x82\x93\xe3\x81\xab\xe3\x81\xa1\xe3\x81\xaf')],
        [u'你好', six.b('\xe4\xbd\xa0\xe5\xa5\xbd')],
        [u'नमस्कार',  six.b('\xe0\xa4\xa8\xe0\xa4\xae\xe0\xa4\xb8\xe0\xa5\x8d\xe0\xa4\x95\xe0\xa4\xbe\xe0\xa4\xb0')],
        [u'안녕하세요', six.b('\xec\x95\x88\xeb\x85\x95\xed\x95\x98\xec\x84\xb8\xec\x9a\x94')],
    ]

    def test_fixEncoding(self):
        """Test the fixEncoding function"""
        for a, b in self.simple_values:
            self.assertEqual(koji.fixEncoding(a), b)
            self.assertEqual(koji.fixEncoding(b), b)
            c = a.encode('utf16')
            self.assertEqual(koji.fixEncoding(c, fallback='utf16'), b)
            d = a[:-3] + u'\x00\x01' + a[-3:]
            self.assertEqual(koji.fixEncoding(d, remove_nonprintable=True), b)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_fixPrint(self, stdout):
        """Test the fixPrint function"""
        expected = ''
        for a, b in self.simple_values:
            if six.PY3:
                self.assertEqual(koji.fixPrint(b), a)
            else:
                self.assertEqual(koji.fixPrint(b), b)
            print(koji.fixPrint(b))
            if six.PY3:
                expected = expected + a + '\n'
            else:
                expected = expected + b + '\n'
        actual = stdout.getvalue()
        self.assertEqual(actual, expected)

    complex_values = [
        # [ value, fixed ]
        [{}, {}],
        [(), ()],
        [None, None],
        [[], []],
        [{u'a': 'a' , 'b' : {'c': u'c\x00'}},
         {six.b('a'): six.b('a') , six.b('b') : {six.b('c'):  six.b('c\x00')}}],
        # iso8859-15 fallback
        ['g\xf3\xf0an daginn', six.b('g\xc3\xb3\xc3\xb0an daginn')],
    ]

    nonprint = [
        ['hello\0world\0', six.b('helloworld')],
        [u'hello\0world\0', six.b('helloworld')],
        [[u'hello\0world\0'], [six.b('helloworld')]],
        [{0: u'hello\0world\0'}, {0: six.b('helloworld')}],
        [[{0: u'hello\0world\0'}], [{0: six.b('helloworld')}]],
    ]

    def test_fixEncodingRecurse(self):
        """Test the fixEncodingRecurse function"""
        for a, b in self.simple_values:
            self.assertEqual(koji.fixEncoding(a), b)
        for a, b in self.complex_values:
            self.assertEqual(koji.fixEncodingRecurse(a), b)
        for a, b in self.nonprint:
            self.assertEqual(koji.fixEncodingRecurse(a, remove_nonprintable=True), b)


if __name__ == '__main__':
    unittest.main()
