# coding=utf-8
from __future__ import absolute_import
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji.util import decode_bytes


class DecodeBytesTestCase(unittest.TestCase):

    DATA = [
            # list of pairs [bytes, string]
            [b'Hello World', u'Hello World'],
             [b'hello', u'hello'],
             [b'hi', u'hi'],
             [b'yo', u'yo'],
             [b"what's up", u"what's up"],
             [b"g'day", u"g'day"],
             [b'back to work', u'back to work'],
             [b'bonjour', u'bonjour'],
             [b'hallo', u'hallo'],
             [b'ciao', u'ciao'],
             [b'hola', u'hola'],
             [b'ol\xc3\xa1', u'olá'],
             [b'dobr\xc3\xbd den', u'dobrý den'],
             [b'zdravstvuite', u'zdravstvuite'],
             [b'g\xc3\xb3\xc3\xb0an daginn', u'góðan daginn'],
             [b'hej', u'hej'],
             [b'tervehdys', u'tervehdys'],
             [b'gr\xc3\xbcezi', u'grüezi'],
             [b'c\xc3\xa9ad m\xc3\xadle f\xc3\xa1ilte', u'céad míle fáilte'],
             [b'hyl\xc3\xb4', u'hylô'],
             [b'bun\xc4\x83 ziua', u'bună ziua'],
             [b'j\xc3\xb3 napot', u'jó napot'],
             [b'dobre dan', u'dobre dan'],
             [b'\xe4\xbd\xa0\xe5\xa5\xbd', u'你好'],
             [b'\xe3\x81\x93\xe3\x82\x93\xe3\x81\xab\xe3\x81\xa1\xe3\x81\xaf', u'こんにちは'],
             [b'\xe0\xa4\xa8\xe0\xa4\xae\xe0\xa4\xb8\xe0\xa5\x8d\xe0\xa4\x95\xe0'
              b'\xa4\xbe\xe0\xa4\xb0',
              u'नमस्कार'],
             [b'\xec\x95\x88\xeb\x85\x95\xed\x95\x98\xec\x84\xb8\xec\x9a\x94', u'안녕하세요']]


    def test_decode_bytes(self):
        for data, expected in self.DATA:
            result = decode_bytes(data)
            self.assertEqual(result, expected)
