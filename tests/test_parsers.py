#!/usr/bin/python

"""Test the __init__.py module"""

import koji
import unittest

class INITTestCase(unittest.TestCase):
    """Main test case container"""

    def test_parse_NVR(self):
        """Test the parse_NVR method"""

        self.assertRaises(AttributeError, koji.parse_NVR, None)
        self.assertRaises(AttributeError, koji.parse_NVR, 1)
        self.assertRaises(AttributeError, koji.parse_NVR, {})
        self.assertRaises(AttributeError, koji.parse_NVR, [])
        self.assertRaises(koji.GenericError, koji.parse_NVR, "")
        self.assertRaises(koji.GenericError, koji.parse_NVR, "foo")
        self.assertRaises(koji.GenericError, koji.parse_NVR, "foo-1")
        self.assertRaises(koji.GenericError, koji.parse_NVR, "foo-1-")
        self.assertRaises(koji.GenericError, koji.parse_NVR, "foo--1")
        self.assertRaises(koji.GenericError, koji.parse_NVR, "--1")
        ret = koji.parse_NVR("foo-1-2")
        self.assertEqual(ret['name'], "foo")
        self.assertEqual(ret['version'], "1")
        self.assertEqual(ret['release'], "2")
        self.assertEqual(ret['epoch'], "")
        ret = koji.parse_NVR("12:foo-1-2")
        self.assertEqual(ret['name'], "foo")
        self.assertEqual(ret['version'], "1")
        self.assertEqual(ret['release'], "2")
        self.assertEqual(ret['epoch'], "12")

    def test_parse_NVRA(self):
        """Test the parse_NVRA method"""

        self.assertRaises(AttributeError, koji.parse_NVRA, None)
        self.assertRaises(AttributeError, koji.parse_NVRA, 1)
        self.assertRaises(AttributeError, koji.parse_NVRA, {})
        self.assertRaises(AttributeError, koji.parse_NVRA, [])
        self.assertRaises(koji.GenericError, koji.parse_NVRA, "")
        self.assertRaises(koji.GenericError, koji.parse_NVRA, "foo")
        self.assertRaises(koji.GenericError, koji.parse_NVRA, "foo-1")
        self.assertRaises(koji.GenericError, koji.parse_NVRA, "foo-1-")
        self.assertRaises(koji.GenericError, koji.parse_NVRA, "foo--1")
        self.assertRaises(koji.GenericError, koji.parse_NVRA, "--1")
        self.assertRaises(koji.GenericError, koji.parse_NVRA, "foo-1-1")
        self.assertRaises(koji.GenericError, koji.parse_NVRA, "foo-1-1.")
        self.assertRaises(koji.GenericError, koji.parse_NVRA, "foo-1.-1")
        ret = koji.parse_NVRA("foo-1-2.i386")
        self.assertEqual(ret['name'], "foo")
        self.assertEqual(ret['version'], "1")
        self.assertEqual(ret['release'], "2")
        self.assertEqual(ret['epoch'], "")
        self.assertEqual(ret['arch'], "i386")
        self.assertEqual(ret['src'], False)
        ret = koji.parse_NVRA("12:foo-1-2.src")
        self.assertEqual(ret['name'], "foo")
        self.assertEqual(ret['version'], "1")
        self.assertEqual(ret['release'], "2")
        self.assertEqual(ret['epoch'], "12")
        self.assertEqual(ret['arch'], "src")
        self.assertEqual(ret['src'], True)

    def test_check_NVR(self):
        """Test the check_NVR function"""
        good = [
            "name-version-release",
            "fnord-5.23-17",
            {'name': 'foo', 'version': '2.2.2', 'release': '1.1'},
            ]
        bad = [
            "this is not an NVR",
            {'name': 'foo', 'version': '2.2.2-a', 'release': '1.1'},
            {'name': 'foo', 'version': '2.2.2', 'release': '1.1-b'},
            ]
        for value in good:
            self.assertEqual(koji.check_NVR(value), True)
        for value in bad:
            self.assertEqual(koji.check_NVR(value), False)
            self.assertRaises(koji.GenericError,
                              koji.check_NVR, value, strict=True)

    def test_check_NVRA(self):
        """Test the check_NVRA function"""
        good = [
            "name-version-release.arch",
            "fnord-5.23-17.x86_64",
            {'name': 'foo', 'version': '2.2.2', 'release': '1.1',
                'arch': 'i686'},
            ]
        bad = [
            "this is not an NVRA",
            "fnord-5.23-17",
            {'name': 'foo', 'version': '2.2.2-a', 'release': '1.1',
                'arch': 'ppc64'},
            {'name': 'foo', 'version': '2.2.2', 'release': '1.1-b',
                'arch': 'x86_64'},
            {'name': 'foo', 'version': '2.2.2', 'release': '1.1',
                'arch': 'x.86.64'},
            ]
        for value in good:
            self.assertEqual(koji.check_NVRA(value), True)
        for value in bad:
            self.assertEqual(koji.check_NVRA(value), False)
            self.assertRaises(koji.GenericError,
                              koji.check_NVRA, value, strict=True)

if __name__ == '__main__':
    unittest.main()
