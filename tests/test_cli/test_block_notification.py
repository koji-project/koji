from __future__ import absolute_import
import koji
import mock
from six.moves import StringIO

from koji_cli.commands import handle_block_notification
from . import utils


class TestBlockNotification(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_block_notification_non_exist_tag(self, stderr):
        tag = 'test-tag'
        expected = "Usage: %s block-notification [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such tag: %s\n" % (self.progname, self.progname, tag)

        self.session.getTagID.side_effect = koji.GenericError
        with self.assertRaises(SystemExit) as ex:
            handle_block_notification(self.options, self.session, ['--tag', tag])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_block_notification_non_exist_pkg(self, stderr):
        pkg = 'test-pkg'
        expected = "Usage: %s block-notification [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such package: %s\n" % (self.progname, self.progname, pkg)

        self.session.getPackageID.return_value = None
        with self.assertRaises(SystemExit) as ex:
            handle_block_notification(self.options, self.session, ['--package', pkg])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
