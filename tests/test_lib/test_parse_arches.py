# coding: utf-8
from __future__ import absolute_import
try:
    import unittest2 as unittest
except ImportError:
    import unittest
import koji

class TestParseArchesString(unittest.TestCase):
    def test_parse_valid_arches(self):
        r = koji.parse_arches('i386', to_list=True)
        self.assertEqual(['i386'], r)

        r = koji.parse_arches('i386 x86_64', to_list=True)
        self.assertEqual(['i386', 'x86_64'], r)

        r = koji.parse_arches('i386 x86_64   ', to_list=True)
        self.assertEqual(['i386', 'x86_64'], r)

        r = koji.parse_arches('i386,x86_64', to_list=True)
        self.assertEqual(['i386', 'x86_64'], r)

    def test_parse_invalid_arches(self):
        with self.assertRaises(koji.GenericError):
            koji.parse_arches(u'ěšč')

        with self.assertRaises(koji.GenericError):
            koji.parse_arches(u'i386;x86_64')

        with self.assertRaises(koji.GenericError):
            koji.parse_arches(u'i386,x86_64', strict=True)
