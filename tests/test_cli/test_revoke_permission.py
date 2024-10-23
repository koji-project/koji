from __future__ import absolute_import
try:
    from unittest import mock
except ImportError:
    import mock
import six
import unittest

from koji_cli.commands import handle_revoke_permission
from . import utils


class TestRevokePermission(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s revoke-permission <permission> <user> [<user> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_revoke_permission(
            self,
            activate_session_mock,
            stdout):
        """Test handle_revoke_permission function"""
        session = mock.MagicMock()
        options = mock.MagicMock()
        perm = 'createrepo'
        users = 'user'

        # Case 1. argument error
        expected = self.format_error_message(
            "Please specify a permission and at least one user")
        for args in [[], [perm]]:
            self.assert_system_exit(
                handle_revoke_permission,
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
            handle_revoke_permission,
            options,
            session,
            [perm, users],
            stderr=expected)

        # Case 3. grant permission with --new
        users = ['user1', 'user2', 'user3']
        session.getUser.side_effect = [
            {'id': 101, 'name': users[0]},
            {'id': 111, 'name': users[1]},
            {'id': 121, 'name': users[2]},
        ]
        handle_revoke_permission(options, session, [perm] + users)
        calls = [mock.call(p, perm) for p in users]
        session.revokePermission.assert_has_calls(calls)

    def test_handle_revoke_permission_help(self):
        self.assert_help(
            handle_revoke_permission,
            """Usage: %s revoke-permission <permission> <user> [<user> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
