from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_grant_cg_access
from . import utils


class TestGrantCGAccess(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s grant-cg-access <user> <content generator>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_grant_cg_access(
            self,
            activate_session_mock,
            stdout):
        """Test handle_grant_cg_access function"""
        session = mock.MagicMock()
        options = mock.MagicMock()
        cg = 'cg'
        user = 'user'

        # Case 1. argument error
        expected = self.format_error_message(
            "Please specify a user and content generator")
        for args in [[], [user]]:
            self.assert_system_exit(
                handle_grant_cg_access,
                options,
                session,
                args,
                stderr=expected,
                activate_session=None)

        # Case 2. user not exists
        expected = self.format_error_message(
            "No such user: %s" % user)
        session.getUser.return_value = None
        self.assert_system_exit(
            handle_grant_cg_access,
            options,
            session,
            [user, cg],
            stderr=expected)

        # Case 3. grant permission with --new
        cg = 'content-generator'
        session.getUser.return_value = {'id': 101, 'name': user}
        handle_grant_cg_access(options, session, [user, cg, '--new'])
        calls = [mock.call(user, cg, create=True)]
        session.grantCGAccess.assert_has_calls(calls)

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
