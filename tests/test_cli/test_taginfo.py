from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_taginfo
from . import utils


class TestTaginfo(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_taginfo_without_option(self, stderr):
        expected = "Usage: %s taginfo [options] <tag> [<tag> ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Please specify a tag\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            anon_handle_taginfo(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_taginfo_non_exist_tag(self, stderr):
        tag = 'test-tag'
        expected = "Usage: %s taginfo [options] <tag> [<tag> ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such tag: %s\n" % (self.progname, self.progname, tag)
        self.session.getBuildConfig.return_value = None
        with self.assertRaises(SystemExit) as cm:
            anon_handle_taginfo(self.options, self.session, [tag])
        self.assertExitCode(cm, 2)
        self.assert_console_message(stderr, expected)
