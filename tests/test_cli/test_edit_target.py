from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_edit_target
from . import utils


class TestEditTarget(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_edit_target_without_option(self, stderr):
        expected = "Usage: %s edit-target [options] <name>\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Please specify a build target\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_edit_target(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    def test_edit_target_non_exist_target(self):
        target = 'test-target'
        expected = "No such build target: %s" % target
        self.session.getBuildTarget.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            handle_edit_target(self.options, self.session, [target])
        self.assertEqual(expected, str(cm.exception))
        self.session.getTag.assert_not_called()
        self.session.editBuildTarget.assert_not_called()

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_edit_target_non_exist_dest_tag(self, stderr):
        target = 'test-target'
        dest_tag = 'test-dest-tag'
        expected = "No such destination tag: %s\n" % dest_tag
        self.session.getTag.return_value = None
        with self.assertRaises(SystemExit) as ex:
            handle_edit_target(self.options, self.session, ['--dest-tag', dest_tag, target])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)
        self.session.editBuildTarget.assert_not_called()
