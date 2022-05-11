from __future__ import absolute_import
import mock
import six
import unittest

from koji_cli.commands import handle_list_permissions
from . import utils


class TestListPermissions(utils.CliTestCase):

    def setUp(self):
        self.error_format = """Usage: %s list-permissions [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

        self.session = mock.MagicMock()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.options = mock.MagicMock()
        self.options.quiet = True
        # Show long diffs in error output...
        self.maxDiff = None
        self.all_perms = [
            {'id': 0, 'name': 'admin', 'description': 'admin-description'},
            {'id': 1, 'name': 'build', 'description': 'build-description'},
            {'id': 2, 'name': 'repo', 'description': 'repo-description'},
            {'id': 3, 'name': 'image', 'description': 'image-description'},
            {'id': 4, 'name': 'livecd', 'description': 'livecd-description'},
            {'id': 5, 'name': 'appliance', 'description': 'appliance-description'},
            {'id': 6, 'name': 'long-permission-appliance',
             'description': 'long-permission-appliance-description'}
        ]
        self.user = 'tester'
        self.userinfo = {'id': 101, 'name': self.user}

    def test_handle_list_permissions_arg_error(self):
        """Test handle_list_permissions argument error (no argument is required)"""
        expected = self.format_error_message("This command takes no arguments")
        self.assert_system_exit(
            handle_list_permissions,
            self.options,
            self.session,
            ['arg-1', 'arg-2'],
            stderr=expected,
            activate_session=None,
            exit_code=2
        )
        self.activate_session_mock.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.getUserPerms.assert_not_called()
        self.session.getPerms.assert_not_called()
        self.session.getAllPerms.assert_not_called()

    def test_handle_list_permissions_user_not_exists(self):
        """Test handle_list_permissions user does not exists"""
        self.session.getUser.return_value = None
        self.assert_system_exit(
            handle_list_permissions,
            self.options,
            self.session,
            ['--user', self.user],
            stderr="No such user: %s" % self.user + "\n",
            activate_session=None,
            exit_code=1
        )
        self.activate_session_mock.assert_called_once()
        self.session.getUser.assert_called_once()
        self.session.getUserPerms.assert_not_called()
        self.session.getPerms.assert_not_called()
        self.session.getAllPerms.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_list_permissions_empty_perms(self, stdout):
        """Test handle_list_permissions that perms is empty"""
        expected = """Permission name   
------------------
"""
        self.options.quiet = False
        self.session.getUser.return_value = self.userinfo
        self.session.getUserPerms.return_value = []
        handle_list_permissions(self.options, self.session, ['--user', self.user])
        self.assert_console_message(stdout, expected)

        self.activate_session_mock.assert_called_once()
        self.session.getUser.assert_called_once()
        self.session.getUserPerms.assert_called_once()
        self.session.getPerms.assert_not_called()
        self.session.getAllPerms.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_list_permissions_user_perms(self, stdout):
        """Test handle_list_permissions user permissions"""
        expected = """admin                    
appliance                
build                    
image                    
livecd                   
long-permission-appliance
repo                     
"""
        perms = [p['name'] for p in self.all_perms[::1]]
        self.session.getUserPerms.return_value = perms
        self.session.getUser.return_value = self.userinfo
        handle_list_permissions(self.options, self.session, ['--user', self.user])
        self.assert_console_message(stdout, expected)

        self.activate_session_mock.assert_called_once()
        self.session.getUser.assert_called_once()
        self.session.getUserPerms.assert_called_once()
        self.session.getPerms.assert_not_called()
        self.session.getAllPerms.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_list_permissions_my_perms(self, stdout):
        """Test handle_list_permissions my permissions"""
        expected = """build             
repo              
"""
        perms = [p['name'] for p in self.all_perms[1:3]]
        self.session.getPerms.return_value = perms
        handle_list_permissions(self.options, self.session, ['--mine'])
        self.assert_console_message(stdout, expected)

        self.activate_session_mock.assert_called_once()
        self.session.getUser.assert_not_called()
        self.session.getUserPerms.assert_not_called()
        self.session.getPerms.assert_called_once()
        self.session.getAllPerms.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_list_permissions_all_perms_quiet_false(self, stdout):
        """Test handle_list_permissions all permissions and quiet is false"""
        self.options.quiet = False
        expected = """Permission name             Description                                       
------------------------------------------------------------------------------
admin                       admin-description
appliance                   appliance-description
build                       build-description
image                       image-description
livecd                      livecd-description
long-permission-appliance   long-permission-appliance-description
repo                        repo-description
"""
        self.session.getAllPerms.return_value = self.all_perms
        handle_list_permissions(self.options, self.session, [])
        self.assert_console_message(stdout, expected)

        self.activate_session_mock.assert_called_once()
        self.session.getUser.assert_not_called()
        self.session.getUserPerms.assert_not_called()
        self.session.getPerms.assert_not_called()
        self.session.getAllPerms.assert_called_once()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_list_permissions_all_perms_length_shorter_eight(self, stdout):
        """Test handle_list_permissions all permissions, length perms shorter than eight"""
        self.options.quiet = False
        expected = """Permission name      Description                                       
-----------------------------------------------------------------------
admin                admin-description
appliance            appliance-description
build                build-description
image                image-description
livecd               livecd-description
repo                 repo-description
"""
        self.session.getAllPerms.return_value = self.all_perms[:-1]
        handle_list_permissions(self.options, self.session, [])
        self.assert_console_message(stdout, expected)

        self.activate_session_mock.assert_called_once()
        self.session.getUser.assert_not_called()
        self.session.getUserPerms.assert_not_called()
        self.session.getPerms.assert_not_called()
        self.session.getAllPerms.assert_called_once()

    def test_handle_list_permissions_help(self):
        self.assert_help(
            handle_list_permissions,
            """Usage: %s list-permissions [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help   show this help message and exit
  --user=USER  List permissions for the given user
  --mine       List your permissions
  --quiet      Do not print the header information
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
