from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_untag_build
from . import utils


class TestUntagBuild(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_untag_build_without_option(self, stderr):
        expected = "Usage: %s untag-build [options] <tag> <pkg> [<pkg> ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: This command takes at least two arguments: " \
                   "a tag name/ID and one or more package " \
                   "n-v-r's\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_untag_build(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_untag_build_without_option_non_latest_force(self, stderr):
        expected = "Usage: %s untag-build [options] <tag> <pkg> [<pkg> ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Please specify a tag\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_untag_build(self.options, self.session, ['--non-latest', '--force'])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_untag_build_non_exist_tag(self, stderr):
        tag = 'test-tag'
        pkg_info = {'id': 9, 'name': 'test-build'}
        expected = "Usage: %s untag-build [options] <tag> <pkg> [<pkg> ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such tag: %s\n" % (self.progname, self.progname, tag)
        self.session.getTag.return_value = None
        with self.assertRaises(SystemExit) as ex:
            handle_untag_build(self.options, self.session, [tag, pkg_info['name']])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
