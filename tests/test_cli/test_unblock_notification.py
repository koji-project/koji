from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_unblock_notification
from . import utils


class TestUnblockNotification(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_unblock_notification_without_args(self, stderr, activate_session):
        expected = "Usage: %s unblock-notification [options] <notification_id> " \
                   "[<notification_id> ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: At least one notification block id has to be specified\n" \
                   % (self.progname, self.progname)

        with self.assertRaises(SystemExit) as ex:
            handle_unblock_notification(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        activate_session.assert_called_once_with(self.session, self.options)

    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_unblock_notification_not_all_integers(self, stderr, activate_session):
        expected = "Usage: %s unblock-notification [options] <notification_id> " \
                   "[<notification_id> ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: All notification block ids has to be integers\n" \
                   % (self.progname, self.progname)

        with self.assertRaises(SystemExit) as ex:
            handle_unblock_notification(self.options, self.session, ['0', 'abcd'])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        activate_session.assert_called_once_with(self.session, self.options)

    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_handle_unblock_notification(self, stdout, activate_session):
        self.options.quiet = False
        expected = "Notification block 0 successfully removed.\n" \
                   "Notification block 1234 successfully removed.\n"
        self.session.deleteNotificationBlock.side_effect = [None, None]
        handle_unblock_notification(self.options, self.session, ['0', '1234'])
        activate_session.assert_called_once_with(self.session, self.options)
        actual = stdout.getvalue()
        print(actual)
        self.assertMultiLineEqual(actual, expected)

    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_handle_unblock_notification_quiet(self, stdout, activate_session):
        expected = ""
        self.options.quiet = True
        self.session.deleteNotificationBlock.side_effect = [None, None]
        handle_unblock_notification(self.options, self.session, ['0', '1234'])
        activate_session.assert_called_once_with(self.session, self.options)
        actual = stdout.getvalue()
        print(actual)
        self.assertMultiLineEqual(actual, expected)
