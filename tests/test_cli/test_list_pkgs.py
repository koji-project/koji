from __future__ import absolute_import

import mock
import copy
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_list_pkgs
from . import utils


class TestListPkgs(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.ensure_connection_mock = mock.patch('koji_cli.commands.ensure_connection').start()
        self.error_format = """Usage: %s list-pkgs [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.owner = 'test-owner'
        self.tag = 'test-tag-2'
        self.pkg = 'test-pkg-2'
        self.userinfo = {'id': 1, 'krb_principals': [], 'name': self.owner,
                         'status': 0, 'usertype': 0}
        self.list_packages = [{'blocked': False,
                               'extra_arches': '',
                               'owner_id': 1,
                               'owner_name': 'test-owner',
                               'package_id': 1,
                               'package_name': 'test-pkg-1',
                               'tag_id': 1,
                               'tag_name': 'test-tag-1'},
                              {'blocked': True,
                               'extra_arches': 'x86_64',
                               'owner_id': 1,
                               'owner_name': 'usertest',
                               'package_id': 2,
                               'package_name': 'test-pkg-2',
                               'tag_id': 2,
                               'tag_name': 'test-tag-2'}, ]
        self.taginfo = {'arches': 'x86_64',
                        'extra': {},
                        'id': 2,
                        'locked': False,
                        'maven_include_all': False,
                        'maven_support': False,
                        'name': 'test-tag-2',
                        'perm': None,
                        'perm_id': None}

    def tearDown(self):
        mock.patch.stopall()

    def test_list_pkgs_non_exist_tag(self):
        self.session.getTag.return_value = None
        self.assert_system_exit(
            anon_handle_list_pkgs,
            self.options, self.session, ['--tag', self.tag],
            stderr=self.format_error_message("No such tag: %s" % self.tag),
            activate_session=None,
            exit_code=2
        )
        self.session.getUser.assert_not_called()
        self.session.listPackages.assert_not_called()
        self.session.getTag.assert_called_once_with(self.tag)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    def test_list_pkgs_non_exist_owner(self):
        self.session.getUser.return_value = None
        self.assert_system_exit(
            anon_handle_list_pkgs,
            self.options, self.session, ['--owner', self.owner],
            stderr=self.format_error_message("No such user: %s" % self.owner),
            activate_session=None,
            exit_code=2
        )
        self.session.getUser.assert_called_once_with(self.owner)
        self.session.listPackages.assert_not_called()
        self.session.getTag.assert_not_called()
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    def test_list_pkgs_argument_error(self):
        self.assert_system_exit(
            anon_handle_list_pkgs,
            self.options, self.session, ['arg'],
            stderr=self.format_error_message("This command takes no arguments"),
            activate_session=None)
        self.ensure_connection_mock.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_pkgs_with_owner_without_quiet(self, stdout):
        self.options.quiet = False
        expected = """Package                 Tag                     Extra Arches     Owner          
----------------------- ----------------------- ---------------- ---------------
test-pkg-1              test-tag-1                               test-owner     
"""
        self.session.getUser.return_value = self.userinfo
        self.session.listPackages.return_value = [self.list_packages[0]]
        rv = anon_handle_list_pkgs(self.options, self.session, ['--owner', self.owner])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.getUser.assert_called_once_with(self.owner)
        self.session.getTag.assert_not_called()
        self.session.listPackages.assert_called_once_with(inherited=True, userID=1,
                                                          with_dups=True)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_pkgs_with_tag_and_pkg_without_quiet_with_blocked(self, stdout):
        self.options.quiet = False
        expected = """Package                 Tag                     Extra Arches     Owner          
----------------------- ----------------------- ---------------- ---------------
test-pkg-2              test-tag-2              x86_64           usertest        [BLOCKED]
"""
        self.session.getTag.return_value = self.taginfo
        self.session.listPackages.return_value = [self.list_packages[1]]
        rv = anon_handle_list_pkgs(self.options, self.session, ['--tag', self.tag,
                                                                '--package', self.pkg,
                                                                '--show-blocked'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.getUser.assert_not_called()
        self.session.getTag.assert_called_once_with(self.tag)
        self.session.listPackages.assert_called_once_with(inherited=True, tagID=2, pkgID=self.pkg,
                                                          with_blocked=True, with_dups=None)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_pkgs_with_tag_and_pkg_without_quiet_with_blocked_extra_arch_none(self, stdout):
        self.options.quiet = False
        list_packages = copy.deepcopy(self.list_packages)
        list_packages[1]['extra_arches'] = None
        expected = """Package                 Tag                     Extra Arches     Owner          
----------------------- ----------------------- ---------------- ---------------
test-pkg-2              test-tag-2                               usertest        [BLOCKED]
"""
        self.session.getTag.return_value = self.taginfo
        self.session.listPackages.return_value = [list_packages[1]]
        rv = anon_handle_list_pkgs(self.options, self.session, ['--tag', self.tag,
                                                                '--package', self.pkg,
                                                                '--show-blocked'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.getUser.assert_not_called()
        self.session.getTag.assert_called_once_with(self.tag)
        self.session.listPackages.assert_called_once_with(inherited=True, tagID=2, pkgID=self.pkg,
                                                          with_blocked=True, with_dups=None)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_pkgs_with_pkg_without_quiet_with_blocked_tag_not_in_pkg(self, stdout):
        self.options.quiet = False
        list_packages = copy.deepcopy(self.list_packages)
        del list_packages[1]['tag_id']
        del list_packages[1]['tag_name']
        expected = """Package                 Tag                     Extra Arches     Owner          
----------------------- ----------------------- ---------------- ---------------
test-pkg-2
"""
        self.session.listPackages.return_value = [list_packages[1]]
        rv = anon_handle_list_pkgs(self.options, self.session, ['--package', self.pkg,
                                                                '--show-blocked'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.getUser.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.listPackages.assert_called_once_with(inherited=True, pkgID=self.pkg,
                                                          with_blocked=True, with_dups=True)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_pkgs_without_options(self, stdout):
        expected = """test-pkg-1
test-pkg-2
"""
        self.session.listPackages.return_value = self.list_packages
        rv = anon_handle_list_pkgs(self.options, self.session, [])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.getUser.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.listPackages.assert_called_once_with(inherited=True, with_dups=True)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_pkgs_not_quiet(self, stdout):
        self.options.quiet = False
        expected = """Package
-----------------------
test-pkg-1
test-pkg-2
"""
        self.session.listPackages.return_value = self.list_packages
        rv = anon_handle_list_pkgs(self.options, self.session, [])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.getUser.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.listPackages.assert_called_once_with(inherited=True, with_dups=True)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    def test_list_pkgs_no_pkg(self):
        self.session.listPackages.return_value = []
        self.session.getTag.return_value = self.taginfo
        self.session.getUser.return_value = self.userinfo
        self.assert_system_exit(
            anon_handle_list_pkgs,
            self.options, self.session, ['--tag', self.tag, '--owner', self.owner],
            stderr="(no matching packages)\n",
            activate_session=None,
            exit_code=1
        )
        self.session.getUser.assert_called_once_with(self.owner)
        self.session.getTag.assert_called_once_with(self.tag)
        self.session.listPackages.assert_called_once_with(inherited=True, with_dups=None,
                                                          tagID=2, userID=1)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_pkgs_without_blocked_empty_result(self, stdout):
        expected = ""
        self.session.getTag.return_value = self.taginfo
        self.session.listPackages.return_value = [self.list_packages[1]]
        rv = anon_handle_list_pkgs(self.options, self.session, ['--tag', self.tag])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.getUser.assert_not_called()
        self.session.getTag.assert_called_once_with(self.tag)
        self.session.listPackages.assert_called_once_with(inherited=True, with_dups=None, tagID=2)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_pkgs_param_error(self, stdout):
        expected = """test-pkg-1              test-tag-1                               test-owner     
test-pkg-2              test-tag-2              x86_64           usertest        [BLOCKED]
"""
        self.session.getTag.return_value = self.taginfo
        self.session.listPackages.side_effect = [koji.ParameterError, self.list_packages]
        rv = anon_handle_list_pkgs(self.options, self.session, ['--show-blocked',
                                                                '--tag', self.tag])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.getUser.assert_not_called()
        self.session.getTag.assert_called_once_with(self.tag)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    def test_list_pkgs_blocked_without_option(self):
        expected = '--show-blocked makes sense only with --tag, --owner or --package'
        self.assert_system_exit(
            anon_handle_list_pkgs,
            self.options, self.session, ['--show-blocked'],
            stderr=self.format_error_message(expected),
            activate_session=None,
            exit_code=2
        )
        self.session.getUser.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.listPackages.assert_not_called()
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('koji.util.eventFromOpts', return_value={'id': 1000,
                                                         'ts': 1000000.11})
    def test_list_pkgs_event_without_option(self, event_from_opts):
        expected = '--event and --ts makes sense only with --tag, --owner or --package'
        self.assert_system_exit(
            anon_handle_list_pkgs,
            self.options, self.session, ['--event', '1000'],
            stderr=self.format_error_message(expected),
            stdout='Querying at event 1000 (Mon Jan 12 13:46:40 1970)\n',
            activate_session=None,
            exit_code=2
        )
        self.session.getUser.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.listPackages.assert_not_called()
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    def test_list_pkgs_help(self):
        self.assert_help(
            anon_handle_list_pkgs,
            """Usage: %s list-pkgs [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help         show this help message and exit
  --owner=OWNER      Specify owner
  --tag=TAG          Specify tag
  --package=PACKAGE  Specify package
  --quiet            Do not print header information
  --noinherit        Don't follow inheritance
  --show-blocked     Show blocked packages
  --show-dups        Show superseded owners
  --event=EVENT#     query at event
  --ts=TIMESTAMP     query at last event before timestamp
  --repo=REPO#       query at event for a repo
""" % self.progname)
