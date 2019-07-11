from __future__ import absolute_import

import os

try:
    import unittest2 as unittest
except ImportError:
    import unittest

import mock

from . import loadcli

cli = loadcli.cli


class TestLoadPlugins(unittest.TestCase):
    @mock.patch('logging.getLogger')
    @mock.patch('os.path.isdir')
    def test_load_plugins(self, isdir, getLogger):
        # skip system path and default user plugin directory check
        isdir.side_effect = lambda path: False if path.startswith('/usr') \
                            or path == os.path.expanduser("~/.koji/plugins") \
                            else True
        cli.load_plugins(os.path.dirname(__file__) + '/data/cli_plugins1:' +
                         os.path.dirname(__file__) + '/data/cli_plugins2')
        self.assertTrue(callable(cli.foobar))
        self.assertTrue(callable(cli.foo2))
        self.assertTrue(hasattr(cli, 'foo6'))
        self.assertFalse(hasattr(cli, 'foo3'))
        self.assertFalse(hasattr(cli, 'foo4'))
        self.assertTrue(hasattr(cli, 'foo5'))
        self.assertFalse(hasattr(cli, 'sth'))
