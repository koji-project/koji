from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_enable_user
from . import utils


class TestEnableUser(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s enable-user <username>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_enable_user(
            self,
            activate_session_mock,
            stdout):
        """Test handle_enable_user function"""
        session = mock.MagicMock()
        options = mock.MagicMock()
        username = 'user'

        # Case 1. no argument error
        expected = self.format_error_message(
            "You must specify the username of the user to enable")
        self.assert_system_exit(
            handle_enable_user,
            options,
            session,
            [],
            stderr=expected,
            activate_session=None)

        # Case 2. Too many argument error
        expected = self.format_error_message(
            "This command only accepts one argument (username)")
        self.assert_system_exit(
            handle_enable_user,
            options,
            session,
            ['user-1', 'user-2', 'user-3'],
            stderr=expected,
            activate_session=None)

        # Case 3. Enable user test
        handle_enable_user(options, session, [username])
        session.enableUser.assert_called_with(username)
        activate_session_mock.assert_called_with(session, options)

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
