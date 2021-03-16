from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_list_tag_inheritance
from . import utils


class TestListTagInheritance(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.tag = 'test-tag'

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_without_option(self, stderr):
        expected = "Usage: %s list-tag-inheritance [options] <tag>\n\n" \
                   "Prints tag inheritance with basic information about links.\n" \
                   "Four flags could be seen in the output:\n" \
                   " M - maxdepth - limits inheritance to n-levels\n" \
                   " F - package filter (packages ignored for inheritance)\n" \
                   " I - intransitive link - inheritance immediately stops here\n" \
                   " N - noconfig - if tag is used in buildroot, its configuration values " \
                   "will not be used\n\n" \
                   "Exact values for maxdepth and package filter can be inquired by " \
                   "taginfo command.\n\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: This command takes exactly one argument: " \
                   "a tag name or ID\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_tag_inheritance(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_with_non_exist_tag(self, stderr):
        expected = "Usage: %s list-tag-inheritance [options] <tag>\n\n" \
                   "Prints tag inheritance with basic information about links.\n" \
                   "Four flags could be seen in the output:\n" \
                   " M - maxdepth - limits inheritance to n-levels\n" \
                   " F - package filter (packages ignored for inheritance)\n" \
                   " I - intransitive link - inheritance immediately stops here\n" \
                   " N - noconfig - if tag is used in buildroot, its configuration values " \
                   "will not be used\n\n" \
                   "Exact values for maxdepth and package filter can be inquired by " \
                   "taginfo command.\n\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such tag: %s\n" % (self.progname, self.progname, self.tag)
        self.session.getTag.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_tag_inheritance(self.options, self.session, [self.tag])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
