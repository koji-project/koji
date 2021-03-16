from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_list_tags
from . import utils


class TestListTags(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_tags_non_exist_package(self, stderr):
        pkg = 'test-pkg'
        expected = "Usage: %s list-tags [options] [pattern]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such package: %s\n" % (self.progname, self.progname, pkg)
        self.session.getPackage.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_tags(self.options, self.session, ['--package', pkg])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_tags_non_exist_build(self, stderr):
        build = 'test-build'
        expected = "Usage: %s list-tags [options] [pattern]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such build: %s\n" % (self.progname, self.progname, build)
        self.session.getBuild.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_tags(self.options, self.session, ['--build', build])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
