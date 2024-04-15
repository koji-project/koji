from __future__ import absolute_import
import mock
import unittest
import koji

from koji_cli.commands import handle_enable_user
from . import utils


class TestEnableUser(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s enable-user <username>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.username = 'user'

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_enable_user_no_argument(self):
        """Test handle_enable_user function"""
        expected = self.format_error_message("You must specify the username of the user to enable")
        self.assert_system_exit(
            handle_enable_user,
            self.options,
            self.session,
            [],
            stderr=expected,
            activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.session.enableUser.assert_not_called()

    def test_handle_enable_user_to_many_arguments(self):
        """Test handle_enable_user function"""
        expected = self.format_error_message("This command only accepts one argument (username)")
        self.assert_system_exit(
            handle_enable_user,
            self.options,
            self.session,
            ['user-1', 'user-2', 'user-3'],
            stderr=expected,
            activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.session.enableUser.assert_not_called()

    def test_handle_enable_user_valid(self):
        """Test handle_enable_user function"""
        handle_enable_user(self.options, self.session, [self.username])
        self.session.enableUser.assert_called_with(self.username)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.enableUser.assert_called_with(self.username)

    def test_handle_enable_user_help(self):
        self.assert_help(
            handle_enable_user,
            """Usage: %s enable-user <username>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
