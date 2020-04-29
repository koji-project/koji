from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_grant_permission
from . import utils


class TestGrantPermission(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s grant-permission [--new] <permission> <user> [<user> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_grant_permission(
            self,
            activate_session_mock,
            stdout):
        """Test handle_grant_permission function"""
        session = mock.MagicMock()
        options = mock.MagicMock()
        perm = 'createrepo'
        users = 'user'

        # Case 1. argument error
        expected = self.format_error_message(
            "Please specify a permission and at least one user")
        for args in [[], [perm]]:
            self.assert_system_exit(
                handle_grant_permission,
                options,
                session,
                args,
                stderr=expected,
                activate_session=None)

        # Case 2. user not exists
        expected = self.format_error_message(
            "No such user: %s" % users)
        session.getUser.return_value = None
        self.assert_system_exit(
            handle_grant_permission,
            options,
            session,
            [perm, users],
            stderr=expected)

        # Case 3. grant permission with --new
        users = ['user1', 'user2', 'user3']
        perm = 'build_iso'
        session.getUser.side_effect = [
            {'id': 101, 'name': users[0]},
            {'id': 111, 'name': users[1]},
            {'id': 121, 'name': users[2]},
        ]
        handle_grant_permission(options, session, [perm, '--new'] + users)
        calls = [mock.call(p, perm, create=True) for p in users]
        session.grantPermission.assert_has_calls(calls)

    def test_handle_grant_permission_help(self):
        self.assert_help(
            handle_grant_permission,
            """Usage: %s grant-permission [--new] <permission> <user> [<user> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
  --new       Create this permission if the permission does not exist
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
