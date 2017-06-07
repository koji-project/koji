from __future__ import absolute_import
import mock
import unittest
from six.moves import StringIO

import koji

from . import loadcli
cli = loadcli.cli

class TestListChannels(unittest.TestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.args = mock.MagicMock()
        self.original_parser = cli.OptionParser
        cli.OptionParser = mock.MagicMock()
        self.parser = cli.OptionParser.return_value
        cli.options = self.options  # globals!!!

    def tearDown(self):
        cli.OptionParser = self.original_parser

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_channels(self, stdout):
        options = mock.MagicMock()
        options.quiet = True
        self.parser.parse_args.return_value = [options, []]

        # mock xmlrpc
        self.session.listChannels.return_value = [
            {'id': 1, 'name': 'default'},
            {'id': 2, 'name': 'test'},
        ]
        self.session.multiCall.return_value = [[[1,2,3]], [[4,5]]]

        cli.anon_handle_list_channels(self.options, self.session, self.args)
        actual = stdout.getvalue()
        expected = 'successfully connected to hub\ndefault             3\ntest                2\n'
        self.assertMultiLineEqual(actual, expected)
