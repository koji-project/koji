from __future__ import absolute_import
import mock
import os
import six
import sys
try:
    import unittest2 as unittest
except ImportError:
    import unittest


from koji_cli.commands import handle_edit_user
from . import utils

progname = os.path.basename(sys.argv[0]) or 'koji'


class TestEditUser(utils.CliTestCase):
    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_edit_user(self, activate_session_mock, stdout):
        user = 'user'
        rename = 'user2'
        args = [user]
        args.append('--rename=' + rename)
        args.append('--add-krb=addedkrb')
        args.append('--remove-krb=removedkrb')
        args.append('--edit-krb=oldkrb=newkrb')
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        # args: user --rename=user --krb=krb
        # expected: success
        rv = handle_edit_user(options, session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.editUser.assert_called_once_with(user, rename,
                                                 [{'new': 'newkrb', 'old': 'oldkrb'},
                                                  {'new': 'addedkrb', 'old': None},
                                                  {'new': None, 'old': 'removedkrb'}])
        self.assertEqual(rv, None)

        stdout.seek(0)
        stdout.truncate()
        session.reset_mock()
        activate_session_mock.reset_mock()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_edit_user_help(self, activate_session_mock, stderr, stdout):
        args = ['--help']
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        # args: --help
        # expected: failed, help info shows
        with self.assertRaises(SystemExit) as cm:
            handle_edit_user(options, session, args)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = """Usage: %s edit-user <username> [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help          show this help message and exit
  --rename=RENAME     Rename the user
  --edit-krb=OLD=NEW  Change kerberos principal of the user
  --add-krb=KRB       Add kerberos principal of the user
  --remove-krb=KRB    Remove kerberos principal of the user
""" % progname
        expected_stderr = ''
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        session.editUser.assert_not_called()
        self.assertEqual(cm.exception.code, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_edit_user_no_arg(self, activate_session_mock, stderr, stdout):
        args = []
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        # args: --help
        # expected: failed, help info shows
        with self.assertRaises(SystemExit) as ex:
            handle_edit_user(options, session, args)
        self.assertExitCode(ex, 2)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = ''
        expected_stderr = """Usage: %(progname)s edit-user <username> [options]
(Specify the --help global option for a list of other help options)

%(progname)s: error: You must specify the username of the user to edit
""" % {'progname': progname}
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        session.editUser.assert_not_called()


if __name__ == '__main__':
    unittest.main()
