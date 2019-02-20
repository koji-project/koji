# coding: utf-8
from __future__ import absolute_import
try:
    import unittest2 as unittest
except ImportError:
    import unittest
import koji
import kojihub

class TestValidateArchesString(unittest.TestCase):
    def test_valid_arches(self):
        kojihub.validate_arches_string('i386')
        kojihub.validate_arches_string('i386 x86_64')
        kojihub.validate_arches_string('i386 x86_64   ')

    def test_invalid_arches(self):
        with self.assertRaises(koji.GenericError):
            kojihub.validate_arches_string(u'ěšč')

        with self.assertRaises(koji.GenericError):
            kojihub.validate_arches_string(u'i386;x86_64')

        with self.assertRaises(koji.GenericError):
            kojihub.validate_arches_string(u'i386,x86_64')

