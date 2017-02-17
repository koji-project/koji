#!/usr/bin/python
# coding=utf-8

"""Test the __init__.py module"""

import koji
import unittest

class FixEncodingTestCase(unittest.TestCase):
    """Main test case container"""

    simple_values = [
        # [ value, fixed ]
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
        [u'नमस्कार', '\xe0\xa4\xa8\xe0\xa4\xae\xe0\xa4\xb8\xe0\xa5\x8d\xe0\xa4\x95\xe0\xa4\xbe\xe0\xa4\xb0'],
        [u'안녕하세요', '\xec\x95\x88\xeb\x85\x95\xed\x95\x98\xec\x84\xb8\xec\x9a\x94'],
    ]

    def test_fixEncoding(self):
        """Test the fixEncoding function"""
        for a, b in self.simple_values:
            self.assertEqual(koji.fixEncoding(a), b)

    complex_values = [
        # [ value, fixed ]
        [{}, {}],
        [(), ()],
        [None, None],
        [[], []],
        [{u'a': 'a' , 'b' : {'c': u'c'}},
         { 'a': 'a' , 'b' : {'c':  'c'}}],
    ]

    def test_fixEncodingRecurse(self):
        """Test the fixEncodingRecurse function"""
        for a, b in self.simple_values:
            self.assertEqual(koji.fixEncoding(a), b)
        for a, b in self.complex_values:
            self.assertEqual(koji.fixEncodingRecurse(a), b)


if __name__ == '__main__':
    unittest.main()
