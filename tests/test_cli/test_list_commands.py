import os
import sys
import unittest

import StringIO as stringio

import mock


# We have to do this craziness because 'import koji' is ambiguous.  Is it the
# koji module, or the koji cli module.  Jump through hoops accordingly.
# http://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
CLI_FILENAME = os.path.dirname(__file__) + "/../../cli/koji"
if sys.version_info[0] >= 3:
    import importlib.util
    spec = importlib.util.spec_from_file_location("koji_cli", CLI_FILENAME)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
else:
    import imp
    cli = imp.load_source('koji_cli', CLI_FILENAME)


class TestListCommands(unittest.TestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.args = mock.MagicMock()
        self.original_parser = cli.OptionParser
        cli.OptionParser = mock.MagicMock()
        self.parser = cli.OptionParser.return_value

    def tearDown(self):
        cli.OptionParser = self.original_parser

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    def test_list_commands(self, stdout):
        cli.list_commands()
        actual = stdout.getvalue()
        actual = actual.replace('nosetests', 'koji')
        filename = os.path.dirname(__file__) + '/data/list-commands.txt'
        with open(filename, 'rb') as f:
            expected = f.read().decode('ascii')
        self.assertMultiLineEqual(actual, expected)

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    def test_handle_admin_help(self, stdout):
        options, arguments = mock.MagicMock(), mock.MagicMock()
        options.admin = True
        self.parser.parse_args.return_value = [options, arguments]
        cli.handle_help(self.options, self.session, self.args)
        actual = stdout.getvalue()
        actual = actual.replace('nosetests', 'koji')
        filename = os.path.dirname(__file__) + '/data/list-commands-admin.txt'
        with open(filename, 'rb') as f:
            expected = f.read().decode('ascii')
        self.assertMultiLineEqual(actual, expected)
