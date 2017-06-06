from __future__ import absolute_import
import unittest
from six.moves import range

from koji_cli.lib import _unique_path

class TestUniquePath(unittest.TestCase):

    def test_unique_path(self):
        for i in range(1000):
            self.assertNotEqual(
                _unique_path('prefix'),
                _unique_path('prefix'))
            self.assertRegexpMatches(
                _unique_path('prefix'),
                '^prefix/\d{10}\.\d{1,7}\.[a-zA-Z]{8}$')

if __name__ == '__main__':
    unittest.main()
