from __future__ import absolute_import
import mock
import os
import rpm
import unittest

import koji

class TestBuildLabel(unittest.TestCase):
    def test_buildLabel(self):
        """Test the buildLabel method"""

        self.assertRaises(AttributeError, koji.buildLabel, None)
        self.assertRaises(AttributeError, koji.buildLabel, 1)
        self.assertRaises(AttributeError, koji.buildLabel, [])

        input = {}
        ret = koji.buildLabel(input)
        self.assertEqual(ret, "None-None-None")

        input = {"name": "foo"}
        ret = koji.buildLabel(input)
        self.assertEqual(ret, "foo-None-None")

        input = {"version": "1.0.2"}
        ret = koji.buildLabel(input)
        self.assertEqual(ret, "None-1.0.2-None")

        input = {"release": "2"}
        ret = koji.buildLabel(input)
        self.assertEqual(ret, "None-None-2")

        input = {"name": "foo", "version": "1.0.2"}
        ret = koji.buildLabel(input)
        self.assertEqual(ret, "foo-1.0.2-None")

        input = {"name": "foo", "release": "2"}
        ret = koji.buildLabel(input)
        self.assertEqual(ret, "foo-None-2")

        input = {"version": "1.0.2", "release": "2"}
        ret = koji.buildLabel(input)
        self.assertEqual(ret, "None-1.0.2-2")

        input = {"name": "foo", "version": "1.0.2", "release": "2"}
        ret = koji.buildLabel(input)
        self.assertEqual(ret, "foo-1.0.2-2")

        input = {"package_name": "bar", "version": "1.0.2", "release": "2"}
        ret = koji.buildLabel(input)
        self.assertEqual(ret, "bar-1.0.2-2")

        input = {
            "package_name": "bar",
            "name": "foo",
            "version": "1.0.2",
            "release": "2"
        }
        ret = koji.buildLabel(input)
        self.assertEqual(ret, "bar-1.0.2-2")

        input = {"epoch": 7, "name": "foo", "version": "1.0.2", "release": "2"}
        ret = koji.buildLabel(input)
        self.assertEqual(ret, "foo-1.0.2-2")

        input = {"epoch": 7, "name": "foo", "version": "1.0.2", "release": "2"}
        ret = koji.buildLabel(input, True)
        self.assertEqual(ret, "7:foo-1.0.2-2")

        input = {"name": "foo", "version": "1.0.2", "release": "2"}
        ret = koji.buildLabel(input, True)
        self.assertEqual(ret, "foo-1.0.2-2")
