from __future__ import absolute_import
import unittest
import sys

from six.moves import range

from koji_cli.lib import unique_path


class TestUniquePath(unittest.TestCase):

    def test_unique_path(self):
        for i in range(1000):
            self.assertNotEqual(unique_path('prefix'), unique_path('prefix'))
            if sys.version_info >= (3, 2):
                return self.assertRegex(
                    unique_path('prefix'), r'^prefix/\d{10}\.\d{1,7}\.[a-zA-Z]{8}$')
            else:
                return self.assertRegexpMatches(
                    unique_path('prefix'), r'^prefix/\d{10}\.\d{1,7}\.[a-zA-Z]{8}$')


if __name__ == '__main__':
    unittest.main()
