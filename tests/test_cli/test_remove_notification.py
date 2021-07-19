from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_remove_notification
from . import utils


class TestAddHost(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_notification(self, activate_session_mock):
        handle_remove_notification(self.options, self.session, ['1', '3', '5'])

        self.session.deleteNotification.assert_has_calls([mock.call(1), mock.call(3),
                                                          mock.call(5)])

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_remove_notification_bogus(self, stderr):
        expected = """Usage: %s remove-notification [options] <notification_id> [<notification_id> ...]
(Specify the --help global option for a list of other help options)

%s: error: All notification ids has to be integers
""" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_remove_notification(self.options, self.session, ['bogus'])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.session.deleteNotification.assert_not_called()

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_remove_notifications_no_args(self, stderr):
        expected = """Usage: %s remove-notification [options] <notification_id> [<notification_id> ...]
(Specify the --help global option for a list of other help options)

%s: error: At least one notification id has to be specified
""" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_remove_notification(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.session.deleteNotification.assert_not_called()

        with self.assertRaises(SystemExit):
            handle_remove_notification(self.options, self.session, [])

        self.session.deleteNotification.assert_not_called()
