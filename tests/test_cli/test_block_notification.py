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

    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_block_notification_with_args(self, stderr, activate_session):
        expected = "Usage: %s block-notification [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: This command takes no arguments\n" \
                   % (self.progname, self.progname)

        with self.assertRaises(SystemExit) as ex:
            handle_block_notification(self.options, self.session, ['1234'])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        activate_session.assert_not_called()

    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_block_notification_with_user_only(self, stderr, activate_session):
        expected = "Usage: %s block-notification [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: One of --tag, --package or --all must be specified.\n" \
                   % (self.progname, self.progname)

        with self.assertRaises(SystemExit) as ex:
            handle_block_notification(self.options, self.session, ['--user', 'testuser'])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        activate_session.assert_not_called()

    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_block_notification_with_user_non_admin_tag(self, stderr, activate_session):
        expected = "Usage: %s block-notification [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: --user requires admin permission\n" \
                   % (self.progname, self.progname)

        self.session.hasPerm.return_value = False
        with self.assertRaises(SystemExit) as ex:
            handle_block_notification(self.options, self.session, ['--user', 'testuser',
                                                                   '--tag', 'tagtest'])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        activate_session.assert_called_once_with(self.session, self.options)

    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_handle_block_notification_with_user_pkg(self, stdout, activate_session):
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
        activate_session.assert_called_once_with(self.session, self.options)

    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_block_notification_without_user_not_logged(self, stderr, activate_session):
        expected = "Usage: %s block-notification [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Please login with authentication or specify --user\n" \
                   % (self.progname, self.progname)

        self.session.getLoggedInUser.return_value = None
        with self.assertRaises(SystemExit) as ex:
            handle_block_notification(self.options, self.session, ['--tag', 'tagtest'])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        activate_session.assert_called_once_with(self.session, self.options)

    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_block_notification_existing_block(self, stderr, activate_session):
        expected = "Usage: %s block-notification [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Notification already exists.\n" \
                   % (self.progname, self.progname)

        self.session.hasPerm.return_value = True
        self.session.getUser.return_value = {'id': 2, 'krb_principals': [],
                                             'name': 'testuser', 'status': 0, 'usertype': 0}
        self.session.getBuildNotificationBlocks.return_value = [{'package_id': 1,
                                                                 'tag_id': 2}]
        self.session.createNotificationBlock.return_value = None
        self.session.getPackageID.return_value = 1
        self.session.getTagID.return_value = 2
        with self.assertRaises(SystemExit) as ex:
            handle_block_notification(self.options, self.session, ['--user', 'testuser',
                                                                   '--package', 'pkgtest',
                                                                   '--tag', 'testtag'])

        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        activate_session.assert_called_once_with(self.session, self.options)
