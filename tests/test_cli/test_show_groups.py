from __future__ import absolute_import

import mock

from koji_cli.commands import anon_handle_show_groups
from . import utils


class TestShowGroups(utils.CliTestCase):

    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.ensure_connection_mock = mock.patch('koji_cli.commands.ensure_connection').start()
        self.error_format = """Usage: %s show-groups [options] <tag>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.tag = 'test-tag'

    def test_show_groups_incorrect_num_of_args(self):
        arguments = []
        self.assert_system_exit(
            anon_handle_show_groups,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message('Incorrect number of arguments'),
            exit_code=2,
            activate_session=None)
        self.ensure_connection_mock.assert_not_called()

    def test_show_groups_show_blocked_and_comps(self):
        arguments = ['--show-blocked', '--comps', self.tag]
        self.assert_system_exit(
            anon_handle_show_groups,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message(
                "--show-blocked doesn't make sense for comps/spec output"),
            exit_code=2,
            activate_session=None)
        self.ensure_connection_mock.assert_not_called()

    def test_show_groups_show_blocked_and_spec(self):
        arguments = ['--show-blocked', '--spec', self.tag]
        self.assert_system_exit(
            anon_handle_show_groups,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message(
                "--show-blocked doesn't make sense for comps/spec output"),
            exit_code=2,
            activate_session=None)
        self.ensure_connection_mock.assert_not_called()

    def test_show_groups_help(self):
        self.assert_help(
            anon_handle_show_groups,
            """Usage: %s show-groups [options] <tag>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help      show this help message and exit
  --comps         Print in comps format
  -x, --expand    Expand groups in comps format
  --spec          Print build spec
  --show-blocked  Show blocked packages
""" % self.progname)
        self.ensure_connection_mock.assert_not_called()
