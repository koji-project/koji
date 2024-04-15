from __future__ import absolute_import
import koji
import mock
from six.moves import StringIO

from koji_cli.commands import handle_add_notification
from . import utils


class TestAddNotification(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.quiet = True
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s add-notification [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_add_notification(self):
        self.session.getPackageID.return_value = 1234
        self.session.getTagID.return_value = 4321
        self.session.getLoggedInUser.return_value = {'id': 678}

        handle_add_notification(self.options, self.session,
                                ['--package', 'pkg_a', '--tag', 'tag_a', '--success-only'])

        self.session.getPackageID.assert_called_once_with('pkg_a')
        self.session.getTagID.assert_called_once_with('tag_a', strict=True)
        self.session.getLoggedInUser.assert_called_once_with()
        self.session.getUser.assert_not_called()
        self.session.createNotification.assert_called_once_with(678, 1234, 4321, True)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_handle_add_notification_no_pkg(self,):
        self.session.getTagID.return_value = 4321
        self.session.getLoggedInUser.return_value = {'id': 678}

        handle_add_notification(self.options, self.session, ['--tag', 'tag_a', '--success-only'])

        self.session.getPackageID.assert_not_called()
        self.session.getTagID.assert_called_once_with('tag_a', strict=True)
        self.session.getLoggedInUser.assert_called_once_with()
        self.session.getUser.assert_not_called()
        self.session.createNotification.assert_called_once_with(678, None, 4321, True)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_handle_add_notification_no_tag(self):
        self.session.getPackageID.return_value = 1234
        self.session.getLoggedInUser.return_value = {'id': 678}

        handle_add_notification(self.options, self.session, ['--package', 'pkg_a'])

        self.session.getPackageID.assert_called_once_with('pkg_a')
        self.session.getTagID.assert_not_called()
        self.session.getLoggedInUser.assert_called_once_with()
        self.session.getUser.assert_not_called()
        self.session.createNotification.assert_called_once_with(678, 1234, None, False)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.exit')
    def test_handle_add_notification_no_pkg_no_tag(self, sys_exit):
        sys_exit.side_effect = SystemExit()
        arguments = ['--success-only']

        self.assert_system_exit(
            handle_add_notification,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message(
                "Command need at least one from --tag or --package options."),
            exit_code=None,
            activate_session=None)

        self.session.getPackageID.assert_not_called()
        self.session.getTagID.assert_not_called()
        self.session.getLoggedInUser.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.createNotification.assert_not_called()
        self.activate_session_mock.assert_not_called()

    @mock.patch('sys.exit')
    def test_handle_add_notification_user_no_admin(self, sys_exit):
        sys_exit.side_effect = SystemExit()
        self.session.hasPerm.return_value = False
        arguments = ['--user', 'username', '--tag', 'tag_a']

        self.assert_system_exit(
            handle_add_notification,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message('--user requires admin permission'),
            exit_code=None,
            activate_session=None)

        self.session.getPackageID.assert_not_called()
        self.session.getTagID.assert_not_called()
        self.session.getLoggedInUser.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.createNotification.assert_not_called()
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_handle_add_notification_user_admin(self):
        self.session.hasPerm.return_value = True
        self.session.getPackageID.return_value = 1234
        self.session.getUser.return_value = {'id': 789}

        handle_add_notification(self.options, self.session,
                                ['--package', 'pkg_a', '--user', 'username'])

        self.session.getPackageID.assert_called_once_with('pkg_a')
        self.session.getTagID.assert_not_called()
        self.session.getLoggedInUser.assert_not_called()
        self.session.getUser.assert_called_once_with('username')
        self.session.createNotification.assert_called_once_with(789, 1234, None, False)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_add_notification_args(self, sys_exit):
        sys_exit.side_effect = SystemExit()
        arguments = ['bogus']
        self.assert_system_exit(
            handle_add_notification,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("This command takes no arguments"),
            exit_code=2,
            activate_session=None)

        self.session.createNotification.assert_not_called()
        self.activate_session_mock.assert_not_called()

    def test_handle_add_notification_non_exist_tag(self):
        tag = 'tag_a'
        arguments = ['--tag', tag]

        self.session.getTagID.side_effect = koji.GenericError
        self.assert_system_exit(
            handle_add_notification,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message('No such tag: %s' % tag),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_handle_add_notification_non_exist_pkg(self):
        pkg = 'pkg_a'
        arguments = ['--package', pkg]

        self.session.getPackageID.return_value = None
        self.assert_system_exit(
            handle_add_notification,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message('No such package: %s' % pkg),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_add_notification_help(self):
        self.assert_help(
            handle_add_notification,
            """Usage: %s add-notification [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help         show this help message and exit
  --user=USER        Add notifications for this user (admin-only)
  --package=PACKAGE  Add notifications for this package
  --tag=TAG          Add notifications for this tag
  --success-only     Enabled notification on successful events only
""" % self.progname)
