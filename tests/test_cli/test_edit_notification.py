from __future__ import absolute_import
import koji
import mock
import unittest
from six.moves import StringIO

from koji_cli.commands import handle_edit_notification
from . import utils


class TestEditNotification(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION


    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_edit_notification(self, activate_session_mock):
        self.session.getPackageID.return_value = 1234
        self.session.getTagID.return_value = 4321
        self.session.getBuildNotification.return_value = {'id': 2345}

        handle_edit_notification(self.options, self.session,
            ['--package', 'pkg_a', '--tag', 'tag_a', '--success-only', '2345'])

        self.session.getPackageID.assert_called_once_with('pkg_a')
        self.session.getTagID.assert_called_once_with('tag_a', strict=True)
        self.session.updateNotification.assert_called_once_with(2345, 1234, 4321, True)


    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_edit_notification_no_pkg(self, activate_session_mock):
        self.session.getBuildNotification.return_value = \
            {'id': 2345, 'package_id': 135, 'success_only': False}

        handle_edit_notification(self.options, self.session,
            ['--tag', '*', '2345'])

        self.session.getPackageID.assert_not_called()
        self.session.getTagID.assert_not_called()
        self.session.updateNotification.assert_called_once_with(2345, 135, None, False)
        self.session.getBuildNotification.assert_called_once_with(2345)


    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_edit_notification_no_tag(self, activate_session_mock):
        self.session.getBuildNotification.return_value = \
            {'id': 2345, 'tag_id': 135, 'success_only': True}

        handle_edit_notification(self.options, self.session,
            ['--package', '*', '--no-success-only', '2345'])

        self.session.getPackageID.assert_not_called()
        self.session.getTagID.assert_not_called()
        self.session.updateNotification.assert_called_once_with(2345, None, 135, False)
        self.session.getBuildNotification.assert_called_once_with(2345)


    @mock.patch('sys.exit')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_edit_notification_bogus(self, sys_stderr, sys_exit):
        sys_exit.side_effect = SystemExit()

        with self.assertRaises(SystemExit):
            handle_edit_notification(self.options, self.session, ['bogus'])

        self.session.updateNotification.assert_not_called()


    @mock.patch('sys.exit')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_edit_notification_no_id(self, sys_stderr, sys_exit):
        sys_exit.side_effect = SystemExit()

        with self.assertRaises(SystemExit):
            handle_edit_notification(self.options, self.session, [])

        self.session.updateNotification.assert_not_called()


    @mock.patch('sys.exit')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_edit_notification_no_opts(self, sys_stderr, sys_exit):
        sys_exit.side_effect = SystemExit()

        with self.assertRaises(SystemExit):
            handle_edit_notification(self.options, self.session, ['123'])

        self.session.updateNotification.assert_not_called()

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_edit_notification_non_exist_tag(self, stderr):
        tag = 'test-tag'
        expected = "Usage: %s edit-notification [options] <notification_id>\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such tag: %s\n" % (self.progname, self.progname, tag)

        self.session.getBuildNotification.return_value = \
            {'id': 2345, 'package_id': 135, 'success_only': False}
        self.session.getTagID.side_effect = koji.GenericError
        with self.assertRaises(SystemExit) as ex:
            handle_edit_notification(self.options, self.session, ['--tag', tag, '2345'])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_edit_notification_non_exist_pkg(self, stderr):
        pkg = 'test-pkg'
        expected = "Usage: %s edit-notification [options] <notification_id>\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such package: %s\n" % (self.progname, self.progname, pkg)
        self.session.getBuildNotification.return_value = \
            {'id': 2345, 'package_id': 135, 'success_only': False}
        self.session.getPackageID.return_value = None

        with self.assertRaises(SystemExit) as ex:
            handle_edit_notification(self.options, self.session, ['--package', pkg, '2345'])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
