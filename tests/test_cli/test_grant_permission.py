from __future__ import absolute_import
import mock
import unittest
import koji

from koji_cli.commands import handle_grant_permission
from . import utils


class TestGrantPermission(utils.CliTestCase):

    def setUp(self):
        # Show long diffs in error output...
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.quiet = True
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s grant-permission [options] <permission> <user> [<user> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.perm = 'createuser'
        self.user = 'user'

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_grant_permission_argument_error(self):
        expected = self.format_error_message(
            "Please specify a permission and at least one user")
        for args in [[], [self.perm]]:
            self.assert_system_exit(
                handle_grant_permission,
                self.options,
                self.session,
                args,
                stderr=expected,
                activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.session.grantPermission.assert_not_called()

    def test_handle_grant_permission_non_exist_user(self):
        expected = self.format_error_message("No such user: %s" % self.user)
        self.session.getUser.return_value = None
        self.assert_system_exit(
            handle_grant_permission,
            self.options,
            self.session,
            [self.perm, self.user],
            stderr=expected)
        self.session.grantPermission.assert_not_called()

    def test_handle_grant_permission_with_new(self):
        users = ['user1', 'user2', 'user3']
        perm = 'build_iso'
        self.session.getUser.side_effect = [
            {'id': 101, 'name': users[0]},
            {'id': 111, 'name': users[1]},
            {'id': 121, 'name': users[2]},
        ]
        handle_grant_permission(self.options, self.session, [perm, '--new'] + users)
        calls = [mock.call(p, perm, create=True) for p in users]
        self.session.grantPermission.assert_has_calls(calls)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_handle_grant_permission_description_without_new(self):
        expected = self.format_error_message(
            "Option new must be specified with option description.")
        self.session.getUser.return_value = {'id': 101, 'name': self.user}
        self.assert_system_exit(
            handle_grant_permission,
            self.options,
            self.session,
            [self.perm, self.user, '--description', 'test-description'],
            stderr=expected)
        self.session.grantPermission.assert_not_called()

    def test_handle_grant_permission_with_new_and_description(self):
        description = 'test-description'
        self.session.getUser.return_value = {'id': 101, 'name': self.user}
        handle_grant_permission(self.options, self.session,
                                ['--new', '--description', description, self.perm, self.user])
        self.session.grantPermission.assert_called_once_with(
            self.user, self.perm, create=True, description=description)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_handle_grant_permission_help(self):
        self.assert_help(
            handle_grant_permission,
            """Usage: %s grant-permission [options] <permission> <user> [<user> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --new                 Create this permission if the permission does not
                        exist
  --description=DESCRIPTION
                        Add description about new permission
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
