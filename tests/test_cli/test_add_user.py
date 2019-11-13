from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_add_user
from . import utils


class TestAddUser(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s add-user <username> [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_user(
            self,
            activate_session_mock,
            stdout):
        """Test handle_add_user function"""
        session = mock.MagicMock()
        options = mock.MagicMock()
        username = 'user'
        user_id = 1001
        principal = 'krb-pricipal'

        # Case 1. no argument error
        expected = self.format_error_message(
            "You must specify the username of the user to add")
        self.assert_system_exit(
            handle_add_user,
            options,
            session,
            [],
            stderr=expected,
            activate_session=None)

        # Case 2. Too many argument error
        expected = self.format_error_message(
            "This command only accepts one argument (username)")
        self.assert_system_exit(
            handle_add_user,
            options,
            session,
            ['user-1', 'user-2', 'user-3'],
            stderr=expected,
            activate_session=None)

        # Case 3. Add user test
        expected = "Added user %s (%i)" % (username, user_id) + "\n"
        arguments = [username, '--principal', principal]
        session.createUser.return_value = user_id
        handle_add_user(options, session, arguments)
        session.createUser.assert_called_with(
            username,
            status=0,
            krb_principal=principal)
        self.assert_console_message(stdout, expected)
        activate_session_mock.assert_called_with(session, options)

        # Case 3. Add blocked user
        arguments = [username, '--principal', principal, '--disable']
        handle_add_user(options, session, arguments)
        session.createUser.assert_called_with(
            username,
            status=1,  # 0: normal, 1: disabled
            krb_principal=principal)
        self.assert_console_message(stdout, expected)
        activate_session_mock.assert_called_with(session, options)

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
