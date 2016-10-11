import unittest

import loadcli

cli = loadcli.cli


class TestUniquePath(unittest.TestCase):

    def test_unique_path(self):
        for i in range(1000):
            self.assertNotEqual(cli._unique_path('prefix'), cli._unique_path('prefix'))
            self.assertRegexpMatches(cli._unique_path('prefix'), '^prefix/\d{10}\.\d{1,6}\.[a-zA-Z]{8}$')

if __name__ == '__main__':
    unittest.main()
