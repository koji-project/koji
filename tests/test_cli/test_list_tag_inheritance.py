from __future__ import absolute_import

import mock

import koji
from koji_cli.commands import anon_handle_list_tag_inheritance
from . import utils


class TestListTagInheritance(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.tag = 'test-tag'
        self.error_format = """Usage: %s list-tag-inheritance [options] <tag>

Prints tag inheritance with basic information about links.
Four flags could be seen in the output:
 M - maxdepth - limits inheritance to n-levels
 F - package filter (packages ignored for inheritance)
 I - intransitive link - inheritance immediately stops here
 N - noconfig - if tag is used in buildroot, its configuration values will not be used

Exact values for maxdepth and package filter can be inquired by taginfo command.

(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def test_without_option(self):
        expected_msg = self.format_error_message("This command takes exactly one argument: "
                                                 "a tag name or ID")
        self.assert_system_exit(
            anon_handle_list_tag_inheritance,
            self.options, self.session, [],
            stderr=expected_msg,
            stdout='',
            activate_session=None,
            exit_code=2)

    def test_with_non_exist_tag(self):
        expected_msg = self.format_error_message("No such tag: %s" % self.tag)
        self.session.getTag.return_value = None
        self.assert_system_exit(
            anon_handle_list_tag_inheritance,
            self.options, self.session, [self.tag],
            stderr=expected_msg,
            stdout='',
            activate_session=None,
            exit_code=2)
        self.session.getTag.assert_called_once_with(self.tag)

    def test_removed_stop_option(self):
        expected_msg = self.format_error_message("--stop option has been removed in 1.26")
        self.session.getTag.return_value = None
        self.assert_system_exit(
            anon_handle_list_tag_inheritance,
            self.options, self.session, ['--stop=test', self.tag],
            stderr=expected_msg,
            stdout='',
            activate_session=None,
            exit_code=2)
        self.session.getTag.assert_not_called()

    def test_removed_jump_option(self):
        expected_msg = self.format_error_message("--jump option has been removed in 1.26")
        self.session.getTag.return_value = None
        self.assert_system_exit(
            anon_handle_list_tag_inheritance,
            self.options, self.session, ['--jump=test', self.tag],
            stderr=expected_msg,
            stdout='',
            activate_session=None,
            exit_code=2)
        self.session.getTag.assert_not_called()

    def test_help(self):
        self.assert_help(
            anon_handle_list_tag_inheritance,
            """Usage: %s list-tag-inheritance [options] <tag>

Prints tag inheritance with basic information about links.
Four flags could be seen in the output:
 M - maxdepth - limits inheritance to n-levels
 F - package filter (packages ignored for inheritance)
 I - intransitive link - inheritance immediately stops here
 N - noconfig - if tag is used in buildroot, its configuration values will not be used

Exact values for maxdepth and package filter can be inquired by taginfo command.

(Specify the --help global option for a list of other help options)

Options:
  -h, --help      show this help message and exit
  --reverse       Process tag's children instead of its parents
  --event=EVENT#  query at event
  --ts=TIMESTAMP  query at last event before timestamp
  --repo=REPO#    query at event for a repo
""" % self.progname)
