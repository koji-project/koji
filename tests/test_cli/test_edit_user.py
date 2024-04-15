from __future__ import absolute_import

import unittest

import six
import mock
import koji


from koji_cli.commands import handle_edit_user
from . import utils


class TestEditUser(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s edit-user <username> [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.user = 'user'
        self.rename = 'user2'

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_edit_user(self, stdout):
        args = [self.user]
        args.append('--rename=' + self.rename)
        args.append('--add-krb=addedkrb')
        args.append('--remove-krb=removedkrb')
        args.append('--edit-krb=oldkrb=newkrb')

        # Run it and check immediate output
        # args: user --rename=user --krb=krb
        # expected: success
        rv = handle_edit_user(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.editUser.assert_called_once_with(self.user, self.rename,
                                                      [{'new': 'newkrb', 'old': 'oldkrb'},
                                                       {'new': 'addedkrb', 'old': None},
                                                       {'new': None, 'old': 'removedkrb'}])
        self.assertEqual(rv, None)

    def test_handle_edit_user_help(self):
        # Run it and check immediate output
        # args: --help
        # expected: failed, help info shows
        self.assert_help(
            handle_edit_user,
            """Usage: %s edit-user <username> [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help          show this help message and exit
  --rename=RENAME     Rename the user
  --edit-krb=OLD=NEW  Change kerberos principal of the user
  --add-krb=KRB       Add kerberos principal of the user
  --remove-krb=KRB    Remove kerberos principal of the user
""" % self.progname)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.editUser.assert_not_called()

    def test_handle_edit_user_no_arg(self):
        # Run it and check immediate output
        # args: --help
        # expected: failed, help info shows
        expected = self.format_error_message("You must specify the username of the user to edit")
        self.assert_system_exit(
            handle_edit_user,
            self.options,
            self.session,
            [],
            stdout='',
            stderr=expected,
            activate_session=None,
            exit_code=2
        )
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.editUser.assert_not_called()

    def test_handle_edit_user_more_arg(self):
        args = ['user', 'user2']
        # Run it and check immediate output
        # args: --help
        # expected: failed, help info shows
        expected = self.format_error_message("This command only accepts one argument (username)")
        self.assert_system_exit(
            handle_edit_user,
            self.options,
            self.session,
            args,
            stdout='',
            stderr=expected,
            activate_session=None,
            exit_code=2
        )
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.editUser.assert_not_called()


if __name__ == '__main__':
    unittest.main()
