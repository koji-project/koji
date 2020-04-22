from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_list_permissions
from . import utils


class TestListPermissions(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s list-permissions [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_list_permissions(
            self,
            activate_session_mock,
            stdout,
            stderr):
        """Test handle_list_permissions function"""
        session = mock.MagicMock()
        options = mock.MagicMock()
        user = 'tester'
        all_perms = [
            {'id': 0, 'name': 'admin'},
            {'id': 1, 'name': 'build'},
            {'id': 2, 'name': 'repo'},
            {'id': 3, 'name': 'image'},
            {'id': 4, 'name': 'livecd'},
            {'id': 5, 'name': 'appliance'}
        ]

        # case 1. argument error (no argument is required)
        expected = self.format_error_message("This command takes no arguments")
        self.assert_system_exit(
            handle_list_permissions,
            options,
            session,
            ['arg-1', 'arg-2'],
            stderr=expected,
            activate_session=None)

        # case 2. user does not exists
        expected = "User %s does not exist" % user + "\n"
        session.getUser.return_value = None
        with self.assertRaises(SystemExit) as ex:
            handle_list_permissions(options, session, ['--user', user])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)

        # case 3. List user permission
        perms = [p['name'] for p in all_perms[::1]]
        session.getUserPerms.return_value = perms
        session.getUser.return_value = {'id': 101, 'name': user}
        expected = "\n".join([p for p in perms]) + "\n"
        handle_list_permissions(options, session, ['--user', user])
        self.assert_console_message(stdout, expected)

        session.getUserPerms.reset_mock()

        # case 4. List my permission
        perms = [p['name'] for p in all_perms[1:3]]
        session.getPerms.return_value = perms
        expected = "\n".join([p for p in perms]) + "\n"
        handle_list_permissions(options, session, ['--mine'])
        self.assert_console_message(stdout, expected)
        session.getUserPerms.assert_not_called()

        session.getPerms.reset_mock()

        # case 5. List all permission
        session.getAllPerms.return_value = all_perms
        expected = "\n".join([p['name'] for p in all_perms]) + "\n"
        handle_list_permissions(options, session, [])
        self.assert_console_message(stdout, expected)
        session.getUserPerms.assert_not_called()
        session.getPerms.assert_not_called()
        session.getAllPerms.assert_called_once()

    def test_handle_list_permissions_help(self):
        self.assert_help(
            handle_list_permissions,
            """Usage: %s list-permissions [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help   show this help message and exit
  --user=USER  List permissions for the given user
  --mine       List your permissions
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
