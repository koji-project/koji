from __future__ import absolute_import
import koji
import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest
from six.moves import StringIO

from koji_cli.commands import handle_add_notification

class TestAddNotification(unittest.TestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.quiet = True
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION


    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_notification(self, activate_session_mock):
        self.session.getPackageID.return_value = 1234
        self.session.getTagID.return_value = 4321
        self.session.getLoggedInUser.return_value = {'id': 678}

        handle_add_notification(self.options, self.session, ['--package', 'pkg_a', '--tag', 'tag_a', '--success-only'])

        self.session.getPackageID.assert_called_once_with('pkg_a')
        self.session.getTagID.assert_called_once_with('tag_a', strict=True)
        self.session.getLoggedInUser.assert_called_once_with()
        self.session.getUser.assert_not_called()
        self.session.createNotification.assert_called_once_with(678, 1234, 4321, True)


    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_notification_no_pkg(self, activate_session_mock):
        self.session.getTagID.return_value = 4321
        self.session.getLoggedInUser.return_value = {'id': 678}

        handle_add_notification(self.options, self.session, ['--tag', 'tag_a', '--success-only'])

        self.session.getPackageID.assert_not_called()
        self.session.getTagID.assert_called_once_with('tag_a', strict=True)
        self.session.getLoggedInUser.assert_called_once_with()
        self.session.getUser.assert_not_called()
        self.session.createNotification.assert_called_once_with(678, None, 4321, True)


    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_notification_no_tag(self, activate_session_mock):
        self.session.getPackageID.return_value = 1234
        self.session.getLoggedInUser.return_value = {'id': 678}

        handle_add_notification(self.options, self.session, ['--package', 'pkg_a'])

        self.session.getPackageID.assert_called_once_with('pkg_a')
        self.session.getTagID.assert_not_called()
        self.session.getLoggedInUser.assert_called_once_with()
        self.session.getUser.assert_not_called()
        self.session.createNotification.assert_called_once_with(678, 1234, None, False)


    @mock.patch('sys.exit')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_add_notification_no_pkg_no_tag(self, sys_stderr, sys_exit):
        sys_exit.side_effect = SystemExit()

        with self.assertRaises(SystemExit):
            handle_add_notification(self.options, self.session, ['--success-only'])

        self.session.getPackageID.assert_not_called()
        self.session.getTagID.assert_not_called()
        self.session.getLoggedInUser.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.createNotification.assert_not_called()


    @mock.patch('sys.exit')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_add_notification_user_no_admin(self, sys_stderr, sys_exit):
        sys_exit.side_effect = SystemExit()
        self.session.hasPerm.return_value = False

        with self.assertRaises(SystemExit):
            handle_add_notification(self.options, self.session, ['--user', 'username', '--tag', 'tag_a'])

        self.session.getPackageID.assert_not_called()
        self.session.getTagID.assert_not_called()
        self.session.getLoggedInUser.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.createNotification.assert_not_called()


    @mock.patch('sys.exit')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_add_notification_user_admin(self, sys_stderr, sys_exit):
        self.session.hasPerm.return_value = True
        self.session.getPackageID.return_value = 1234
        self.session.getUser.return_value = {'id': 789}

        handle_add_notification(self.options, self.session, ['--package', 'pkg_a', '--user', 'username'])

        self.session.getPackageID.assert_called_once_with('pkg_a')
        self.session.getTagID.assert_not_called()
        self.session.getLoggedInUser.assert_not_called()
        self.session.getUser.assert_called_once_with('username')
        self.session.createNotification.assert_called_once_with(789, 1234, None, False)


    @mock.patch('sys.exit')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_add_notification_args(self, sys_stderr, sys_exit):
        sys_exit.side_effect = SystemExit()

        with self.assertRaises(SystemExit):
            handle_add_notification(self.options, self.session, ['bogus'])

        self.session.createNotification.assert_not_called()
