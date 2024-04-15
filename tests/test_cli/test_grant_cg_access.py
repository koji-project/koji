from __future__ import absolute_import
import mock
import unittest

from koji_cli.commands import handle_grant_cg_access
from . import utils


class TestGrantCGAccess(utils.CliTestCase):

    def setUp(self):
        self.error_format = """Usage: %s grant-cg-access <user> <content generator>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.quiet = False
        self.session = mock.MagicMock()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.cg = 'cg'
        self.user = 'user'

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_grant_cg_access_arg_error(self):
        """Test handle_grant_cg_access function"""
        expected = self.format_error_message("Please specify a user and content generator")
        for args in [[], [self.user]]:
            self.assert_system_exit(
                handle_grant_cg_access,
                self.options,
                self.session,
                args,
                stderr=expected,
                activate_session=None,
                exit_code=2)
        self.activate_session_mock.assert_not_called()
        self.session.grantCGAccess.assert_not_called()

    def test_handle_grant_cg_access_non_exist_user(self):
        """Test handle_grant_cg_access function"""
        expected = self.format_error_message("No such user: %s" % self.user)
        self.session.getUser.return_value = None
        self.assert_system_exit(
            handle_grant_cg_access,
            self.options,
            self.session,
            [self.user, self.cg],
            stderr=expected,
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getUser.assert_called_once_with(self.user)
        self.session.grantCGAccess.assert_not_called()

    def test_handle_grant_cg_access_valid(self):
        """Test handle_grant_cg_access function"""
        cg = 'content-generator'
        self.session.getUser.return_value = {'id': 101, 'name': self.user}
        handle_grant_cg_access(self.options, self.session, [self.user, cg, '--new'])
        calls = [mock.call(self.user, cg, create=True)]
        self.session.grantCGAccess.assert_has_calls(calls)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getUser.assert_called_once_with(self.user)

    def test_handle_grant_cg_access_help(self):
        self.assert_help(
            handle_grant_cg_access,
            """Usage: %s grant-cg-access <user> <content generator>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
  --new       Create a new content generator
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
