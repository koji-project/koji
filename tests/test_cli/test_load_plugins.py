from __future__ import absolute_import
import mock
import os
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from . import loadcli
cli = loadcli.cli


class TestLoadPlugins(unittest.TestCase):

    @mock.patch('logging.getLogger')
    def test_load_plugins(self, getLogger):
        options = mock.MagicMock()
        cli.load_plugins(options, os.path.dirname(__file__) + '/data/plugins')
        self.assertTrue(callable(cli.foobar))
        self.assertTrue(callable(cli.foo2))
        self.assertFalse(hasattr(cli, 'foo3'))
        self.assertFalse(hasattr(cli, 'foo4'))
        self.assertFalse(hasattr(cli, 'sth'))
