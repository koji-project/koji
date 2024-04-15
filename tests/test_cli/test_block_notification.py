from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_block_notification
from . import utils


class TestBlockNotification(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s block-notification [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_block_notification_non_exist_tag(self):
        tag = 'test-tag'
        arguments = ['--tag', tag]

        self.session.getTagID.side_effect = koji.GenericError
        self.assert_system_exit(
            handle_block_notification,
            self.options, self.session, arguments,
            stderr=self.format_error_message("No such tag: %s" % tag),
            stdout='',
            activate_session=None,
            exit_code=2)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_handle_block_notification_non_exist_pkg(self):
        pkg = 'test-pkg'
        arguments = ['--package', pkg]
        self.session.getPackageID.return_value = None
        self.assert_system_exit(
            handle_block_notification,
            self.options, self.session, arguments,
            stderr=self.format_error_message("No such package: %s" % pkg),
            stdout='',
            activate_session=None,
            exit_code=2)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_handle_block_notification_with_args(self):
        arguments = ['1234']
        self.assert_system_exit(
            handle_block_notification,
            self.options, self.session, arguments,
            stderr=self.format_error_message("This command takes no arguments"),
            stdout='',
            activate_session=None,
            exit_code=2)
        self.activate_session_mock.assert_not_called()

    def test_handle_block_notification_with_user_only(self):
        arguments = ['--user', 'testuser']
        self.assert_system_exit(
            handle_block_notification,
            self.options, self.session, arguments,
            stderr=self.format_error_message(
                "One of --tag, --package or --all must be specified."),
            stdout='',
            activate_session=None,
            exit_code=2)
        self.activate_session_mock.assert_not_called()

    def test_handle_block_notification_with_user_non_admin_tag(self):
        arguments = ['--user', 'testuser', '--tag', 'tagtest']
        self.session.hasPerm.return_value = False
        self.assert_system_exit(
            handle_block_notification,
            self.options, self.session, arguments,
            stderr=self.format_error_message("--user requires admin permission"),
            stdout='',
            activate_session=None,
            exit_code=2)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_handle_block_notification_with_user_pkg(self, stdout):
        expected = ""

        self.session.hasPerm.return_value = True
        self.session.getUser.return_value = {'id': 2, 'krb_principals': [],
                                             'name': 'testuser', 'status': 0, 'usertype': 0}
        self.session.getBuildNotificationBlocks.return_value = []
        self.session.createNotificationBlock.return_value = None
        self.session.getPackageID.return_value = 1
        handle_block_notification(self.options, self.session, ['--user', 'testuser',
                                                               '--package', 'pkgtest'])

        self.assert_console_message(stdout, expected)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_handle_block_notification_without_user_not_logged(self):
        arguments = ['--tag', 'tagtest']
        self.session.getLoggedInUser.return_value = None
        self.assert_system_exit(
            handle_block_notification,
            self.options, self.session, arguments,
            stderr=self.format_error_message("Please login with authentication or specify --user"),
            stdout='',
            activate_session=None,
            exit_code=2)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_handle_block_notification_existing_block(self):
        self.session.hasPerm.return_value = True
        self.session.getUser.return_value = {'id': 2, 'krb_principals': [],
                                             'name': 'testuser', 'status': 0, 'usertype': 0}
        self.session.getBuildNotificationBlocks.return_value = [{'package_id': 1,
                                                                 'tag_id': 2}]
        self.session.createNotificationBlock.return_value = None
        self.session.getPackageID.return_value = 1
        self.session.getTagID.return_value = 2
        arguments = ['--user', 'testuser', '--package', 'pkgtest', '--tag', 'testtag']
        self.assert_system_exit(
            handle_block_notification,
            self.options, self.session, arguments,
            stderr=self.format_error_message("Notification already exists."),
            stdout='',
            activate_session=None,
            exit_code=2)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_block_notification_help(self):
        self.assert_help(
            handle_block_notification,
            """Usage: %s block-notification [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help         show this help message and exit
  --user=USER        Block notifications for this user (admin-only)
  --package=PACKAGE  Block notifications for this package
  --tag=TAG          Block notifications for this tag
  --all              Block all notification for this user
""" % self.progname)
