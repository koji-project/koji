from __future__ import absolute_import
import mock
import six
import unittest
import koji

from koji_cli.commands import handle_add_user
from . import utils


class TestAddUser(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s add-user <username> [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_add_user(self, stdout):
        """Test handle_add_user function"""
        username = 'user'
        user_id = 1001
        principal = 'krb-pricipal'

        # Case 1. no argument error
        expected = self.format_error_message(
            "You must specify the username of the user to add")
        self.assert_system_exit(
            handle_add_user,
            self.options, self.session, [],
            stdout='',
            stderr=expected,
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.activate_session_mock.reset_mock()

        # Case 2. Too many argument error
        expected = self.format_error_message(
            "This command only accepts one argument (username)")
        self.assert_system_exit(
            handle_add_user,
            self.options, self.session, ['user-1', 'user-2', 'user-3'],
            stdout='',
            stderr=expected,
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.activate_session_mock.reset_mock()

        # Case 3. Add user test
        expected = "Added user %s (%i)" % (username, user_id) + "\n"
        arguments = [username, '--principal', principal]
        self.session.createUser.return_value = user_id
        handle_add_user(self.options, self.session, arguments)
        self.session.createUser.assert_called_with(
            username,
            status=0,
            krb_principal=principal)
        self.assert_console_message(stdout, expected)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.activate_session_mock.reset_mock()

        # Case 3. Add blocked user
        arguments = [username, '--principal', principal, '--disable']
        handle_add_user(self.options, self.session, arguments)
        self.session.createUser.assert_called_with(
            username,
            status=1,  # 0: normal, 1: disabled
            krb_principal=principal)
        self.assert_console_message(stdout, expected)
        self.activate_session_mock.assert_called_with(self.session, self.options)

    def test_handle_add_user_help(self):
        self.assert_help(
            handle_add_user,
            """Usage: %s add-user <username> [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --principal=PRINCIPAL
                        The Kerberos principal for this user
  --disable             Prohibit logins by this user
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
