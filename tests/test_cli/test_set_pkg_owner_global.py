from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_set_pkg_owner_global
from . import utils


class TestSetPkgOwnerGlobal(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    def test_set_pkg_owner_global_help(self):
        self.assert_help(
            handle_set_pkg_owner_global,
            """Usage: %s set-pkg-owner-global [options] <owner> <package> [<package> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --verbose             List changes
  --test                Test mode
  --old-user=OLD_USER, --from=OLD_USER
                        Only change ownership for packages belonging to this
                        user
""" % self.progname)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_set_pkg_owner_global_without_arguments(self, stderr):
        expected = """Usage: %s set-pkg-owner-global [options] <owner> <package> [<package> ...]
(Specify the --help global option for a list of other help options)

%s: error: Please specify an owner and at least one package
""" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_set_pkg_owner_global(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.session.listPackages.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.packageListSetOwner.assert_not_called()

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_set_pkg_owner_global_old_user_spefify_owner(self, stderr):
        expected = """Usage: %s set-pkg-owner-global [options] <owner> <package> [<package> ...]
(Specify the --help global option for a list of other help options)

%s: error: Please specify an owner
""" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_set_pkg_owner_global(self.options, self.session, ['--old-user', 'test-user'])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.session.listPackages.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.packageListSetOwner.assert_not_called()

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_set_pkg_owner_global_non_exist_owner(self, stderr):
        expected = "No such user: user\n"
        self.session.getUser.return_value = None
        with self.assertRaises(SystemExit) as ex:
            handle_set_pkg_owner_global(self.options, self.session, ['user', 'test-package'])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)
        self.session.listPackages.assert_not_called()
        self.session.getUser.assert_called_once_with('user')
        self.session.packageListSetOwner.assert_not_called()

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_set_pkg_owner_global_old_user_non_exist_user(self, stderr):
        expected = "No such user: test-user\n"
        user_info = [{'id': 1, 'krb_principals': [], 'name': 'user', 'status': 0,
                      'usertype': 0},
                     None]
        self.session.getUser.side_effect = user_info
        with self.assertRaises(SystemExit) as ex:
            handle_set_pkg_owner_global(self.options, self.session, ['--old-user', 'test-user',
                                                                     'user', 'test-package'])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)
        self.session.listPackages.assert_not_called()
        expected_calls = [mock.call('user'), mock.call('test-user')]
        self.session.getUser.assert_has_calls(expected_calls)
        self.session.packageListSetOwner.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_set_pkg_owner_global_without_pkgs(self, stdout):
        expected = "No data for package test-package\n"
        user_info = [{'id': 1, 'krb_principals': [], 'name': 'user', 'status': 0,
                      'usertype': 0}]
        self.session.getUser.return_value = user_info
        self.session.listPackages.return_value = []
        handle_set_pkg_owner_global(self.options, self.session, ['user', 'test-package'])
        self.assert_console_message(stdout, expected)
        self.session.listPackages.assert_called_once_with(pkgID='test-package', with_dups=True)
        self.session.getUser.assert_called_once_with('user')
        self.session.packageListSetOwner.assert_not_called()

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_set_pkg_owner_global_user_without_pkgs(self, stderr):
        expected = "No data for user test-user\n"
        user_info = [{'id': 1, 'krb_principals': [], 'name': 'user', 'status': 0,
                      'usertype': 0},
                     {'id': 2, 'krb_principals': [], 'name': 'test-user',
                      'status': 0, 'usertype': 0}]
        self.session.getUser.side_effect = user_info
        self.session.listPackages.return_value = []
        with self.assertRaises(SystemExit) as ex:
            handle_set_pkg_owner_global(self.options, self.session, ['--old-user', 'test-user',
                                                                     'user'])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)
        self.session.listPackages.assert_called_once_with(userID=2, with_dups=True)
        expected_calls = [mock.call('user'), mock.call('test-user')]
        self.session.getUser.assert_has_calls(expected_calls)
        self.session.packageListSetOwner.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_set_pkg_owner_global_test(self, stdout):
        expected = "Would have changed owner for test-package-123 in tag test-tag: kojiadmin" \
                   " -> user\n"
        user_info = [{'id': 2, 'krb_principals': [], 'name': 'user', 'status': 0,
                      'usertype': 0},
                     {'id': 1, 'krb_principals': [], 'name': 'kojiadmin', 'status': 0,
                      'usertype': 0},
                     ]
        self.session.getUser.side_effect = user_info
        self.session.listPackages.return_value = [
            {'blocked': False,
             'extra_arches': '',
             'owner_id': 1,
             'owner_name': 'kojiadmin',
             'package_id': 1,
             'package_name': 'test-package-123',
             'tag_id': 18,
             'tag_name': 'test-tag'}]

        handle_set_pkg_owner_global(self.options, self.session, ['user', '--test',
                                                                 '--old-user', 'kojiadmin'])
        self.assert_console_message(stdout, expected)
        self.session.listPackages.assert_called_once_with(userID=1, with_dups=True)
        expected_calls = [mock.call('user'), mock.call('kojiadmin')]
        self.session.getUser.assert_has_calls(expected_calls)
        self.session.packageListSetOwner.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_set_pkg_owner_global_verbose_preserving_owner(self, stdout):
        expected = "Preserving owner=user for package test-package in tag test-tag\n"
        user_info = {'id': 1, 'krb_principals': [], 'name': 'user', 'status': 0, 'usertype': 0}
        self.session.getUser.return_value = user_info
        self.session.listPackages.return_value = [
            {'blocked': False,
             'extra_arches': '',
             'owner_id': 1,
             'owner_name': 'user',
             'package_id': 1,
             'package_name': 'test-package-123',
             'tag_id': 18,
             'tag_name': 'test-tag'}]

        handle_set_pkg_owner_global(self.options, self.session, ['user', 'test-package',
                                                                 '--verbose'])
        self.assert_console_message(stdout, expected)
        self.session.listPackages.assert_called_once_with(pkgID='test-package', with_dups=True)
        self.session.getUser.assert_called_once_with('user')
        self.session.packageListSetOwner.assert_not_called()

    def test_set_pkg_owner_global_verbose_valid(self, ):
        user_info = {'id': 1, 'krb_principals': [], 'name': 'user', 'status': 0,
                     'usertype': 0}
        self.session.getUser.return_value = user_info
        self.session.listPackages.return_value = [
            {'blocked': False,
             'extra_arches': '',
             'owner_id': 2,
             'owner_name': 'kojiadmin',
             'package_id': 1,
             'package_name': 'test-package-123',
             'tag_id': 18,
             'tag_name': 'test-tag'}]
        self.session.packageListSetOwner.return_value = None
        handle_set_pkg_owner_global(self.options, self.session, ['user', 'test-package',
                                                                 '--verbose'])
        self.session.packageListSetOwner.assert_called_once_with(18, 'test-package-123', 1)
        self.session.listPackages.assert_called_once_with(pkgID='test-package', with_dups=True)
        self.session.getUser.assert_called_once_with('user')
