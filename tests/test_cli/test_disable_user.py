from __future__ import absolute_import
import mock
import six
import unittest

from koji_cli.commands import handle_disable_user
from . import utils


class TestDisableUser(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.options = mock.MagicMock()
        self.options.quiet = False
        self.session = mock.MagicMock()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.username = 'user'
        self.error_format = """Usage: %s disable-user <username>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def test_handle_disable_user_no_argument(self):
        """Test handle_disable_user function"""
        expected = self.format_error_message(
            "You must specify the username of the user to disable")
        self.assert_system_exit(
            handle_disable_user,
            self.options,
            self.session,
            [],
            stderr=expected,
            activate_session=None,
            exit_code=2
        )
        self.activate_session_mock.assert_not_called()

    def test_handle_disable_user_many_arguments(self):
        """Test handle_disable_user function"""
        expected = self.format_error_message(
            "This command only accepts one argument (username)")
        self.assert_system_exit(
            handle_disable_user,
            self.options,
            self.session,
            ['user-1', 'user-2', 'user-3'],
            stderr=expected,
            activate_session=None,
            exit_code=2
        )
        self.activate_session_mock.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_disable_user_valid(self, stdout):
        handle_disable_user(self.options, self.session, [self.username])
        self.session.disableUser.assert_called_with(self.username)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.assert_console_message(stdout, '')

    def test_handle_disable_user_help(self):
        self.assert_help(
            handle_disable_user,
            """Usage: %s disable-user <username>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
