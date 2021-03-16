from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_remove_tag
from . import utils


class TestRemoveTag(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_remove_tag_without_option(self, stderr):
        expected = "Usage: %s remove-tag [options] <name>\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Please specify a tag to remove\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_remove_tag(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_remove_tag_non_exist_tag(self, stderr):
        tag = 'test-tag'
        expected = "No such tag: %s\n" % tag
        self.session.getTag.return_value = None
        with self.assertRaises(SystemExit) as ex:
            handle_remove_tag(self.options, self.session, [tag])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)
