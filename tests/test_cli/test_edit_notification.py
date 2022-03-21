from __future__ import absolute_import
import koji
import mock

from koji_cli.commands import handle_edit_notification
from . import utils


class TestEditNotification(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s edit-notification [options] <notification_id>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def test_handle_edit_notification(self):
        self.session.getPackageID.return_value = 1234
        self.session.getTagID.return_value = 4321
        self.session.getBuildNotification.return_value = {'id': 2345}

        handle_edit_notification(self.options, self.session,
                                 ['--package', 'pkg_a', '--tag', 'tag_a',
                                  '--success-only', '2345'])

        self.session.getBuildNotification.assert_called_once_with(2345)
        self.session.getPackageID.assert_called_once_with('pkg_a')
        self.session.getTagID.assert_called_once_with('tag_a', strict=True)
        self.session.updateNotification.assert_called_once_with(2345, 1234, 4321, True)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_handle_edit_notification_no_pkg(self):
        self.session.getBuildNotification.return_value = \
            {'id': 2345, 'package_id': 135, 'success_only': False}

        handle_edit_notification(self.options, self.session, ['--tag', '*', '2345'])

        self.session.getPackageID.assert_not_called()
        self.session.getTagID.assert_not_called()
        self.session.updateNotification.assert_called_once_with(2345, 135, None, False)
        self.session.getBuildNotification.assert_called_once_with(2345)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_handle_edit_notification_no_tag(self):
        self.session.getBuildNotification.return_value = \
            {'id': 2345, 'tag_id': 135, 'success_only': True}

        handle_edit_notification(self.options, self.session,
                                 ['--package', '*', '--no-success-only', '2345'])

        self.session.getPackageID.assert_not_called()
        self.session.getTagID.assert_not_called()
        self.session.updateNotification.assert_called_once_with(2345, None, 135, False)
        self.session.getBuildNotification.assert_called_once_with(2345)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_handle_edit_notification_bogus(self):
        expected = self.format_error_message("Notification ID has to be numeric")
        self.assert_system_exit(
            handle_edit_notification,
            self.options,
            self.session,
            ['bogus'],
            stdout='',
            stderr=expected,
            activate_session=None,
            exit_code=2
        )
        self.session.updateNotification.assert_not_called()
        self.session.getPackageID.assert_not_called()
        self.session.getTagID.assert_not_called()
        self.session.getBuildNotification.assert_not_called()
        self.activate_session_mock.assert_not_called()

    def test_handle_edit_notification_no_id(self):
        expected = self.format_error_message("Only argument is notification ID")
        self.assert_system_exit(
            handle_edit_notification,
            self.options,
            self.session,
            [],
            stdout='',
            stderr=expected,
            activate_session=None,
            exit_code=2
        )

        self.session.updateNotification.assert_not_called()
        self.session.getPackageID.assert_not_called()
        self.session.getTagID.assert_not_called()
        self.session.getBuildNotification.assert_not_called()
        self.activate_session_mock.assert_not_called()

    def test_handle_edit_notification_no_opts(self):
        expected = self.format_error_message("Command need at least one option")
        self.assert_system_exit(
            handle_edit_notification,
            self.options,
            self.session,
            ['123'],
            stdout='',
            stderr=expected,
            activate_session=None,
            exit_code=2
        )

        self.session.updateNotification.assert_not_called()
        self.session.getPackageID.assert_not_called()
        self.session.getTagID.assert_not_called()
        self.session.getBuildNotification.assert_not_called()
        self.activate_session_mock.assert_not_called()

    def test_handle_edit_notification_non_exist_tag(self):
        tag = 'test-tag'
        expected = self.format_error_message("No such tag: %s" % tag)

        self.session.getBuildNotification.return_value = \
            {'id': 2345, 'package_id': 135, 'success_only': False}
        self.session.getTagID.side_effect = koji.GenericError
        self.assert_system_exit(
            handle_edit_notification,
            self.options,
            self.session,
            ['--tag', tag, '2345'],
            stdout='',
            stderr=expected,
            activate_session=None,
            exit_code=2
        )
        self.session.getPackageID.assert_not_called()
        self.session.getTagID.assert_called_once_with(tag, strict=True)
        self.session.getBuildNotification.assert_called_once_with(2345)
        self.session.updateNotification.assert_not_called()
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_handle_edit_notification_non_exist_pkg(self):
        pkg = 'test-pkg'
        expected = self.format_error_message("No such package: %s" % pkg)
        self.session.getBuildNotification.return_value = \
            {'id': 2345, 'package_id': 135, 'success_only': False}
        self.session.getPackageID.return_value = None
        self.assert_system_exit(
            handle_edit_notification,
            self.options,
            self.session,
            ['--package', pkg, '2345'],
            stdout='',
            stderr=expected,
            activate_session=None,
            exit_code=2
        )
        self.session.getPackageID.assert_called_once_with(pkg)
        self.session.getTagID.assert_not_called()
        self.session.getBuildNotification.assert_called_once_with(2345)
        self.session.updateNotification.assert_not_called()
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
