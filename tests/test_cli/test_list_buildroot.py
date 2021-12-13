from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_list_buildroot
from . import utils


class TestListBuilds(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.ensure_connection_mock = mock.patch('koji_cli.commands.ensure_connection').start()

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_buildroot_with_paths_option(self, stderr):
        expected = """Usage: %s list-buildroot [options] <buildroot-id>
(Specify the --help global option for a list of other help options)

%s: error: --paths option is deprecated and will be removed in 1.30
""" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_buildroot(self.options, self.session, ['--paths', '1'])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_buildroot_without_args(self, stderr):
        expected = """Usage: %s list-buildroot [options] <buildroot-id>
(Specify the --help global option for a list of other help options)

%s: error: Incorrect number of arguments
""" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_buildroot(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.ensure_connection_mock.assert_not_called()

    def test_list_buildroot_help(self):
        self.assert_help(
            anon_handle_list_buildroot,
            """Usage: %s list-buildroot [options] <buildroot-id>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help     show this help message and exit
  --built        Show the built rpms
  -v, --verbose  Show more information
""" % self.progname)
        self.ensure_connection_mock.assert_not_called()
