from __future__ import absolute_import
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from six.moves import range

from koji_cli.lib import unique_path

class TestUniquePath(unittest.TestCase):

    def test_unique_path(self):
        for i in range(1000):
            self.assertNotEqual(
                unique_path('prefix'),
                unique_path('prefix'))
            self.assertRegexpMatches(
                unique_path('prefix'),
                '^prefix/\d{10}\.\d{1,7}\.[a-zA-Z]{8}$')

if __name__ == '__main__':
    unittest.main()
