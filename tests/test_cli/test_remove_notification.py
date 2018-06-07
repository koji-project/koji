from __future__ import absolute_import
import koji
import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from six.moves import StringIO

from koji_cli.commands import handle_remove_notification

class TestAddHost(unittest.TestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION


    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_notification(self, activate_session_mock):
        handle_remove_notification(self.options, self.session, ['1', '3', '5'])

        self.session.deleteNotification.assert_has_calls([mock.call(1), mock.call(3), mock.call(5)])


    @mock.patch('sys.exit')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_remove_notification_bogus(self, sys_stderr, sys_exit):
        sys_exit.side_effect = SystemExit()

        with self.assertRaises(SystemExit):
            handle_remove_notification(self.options, self.session, ['bogus'])

        self.session.deleteNotification.assert_not_called()


    @mock.patch('sys.exit')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_remove_notifications_no_args(self, sys_stderr, sys_exit):
        sys_exit.side_effect = SystemExit()

        with self.assertRaises(SystemExit):
            handle_remove_notification(self.options, self.session, [])

        self.session.deleteNotification.assert_not_called()
