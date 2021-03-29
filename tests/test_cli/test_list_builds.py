from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_list_builds
from . import utils


class TestListBuilds(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.user_info = {'id': 1, 'name': 'kojiadmin', 'status': 0, 'usertype': 0,
                          'krb_principals': []}

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_builds_without_option(self, stderr):
        expected = "Usage: %s list-builds [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Filter must be provided for list\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_builds(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_builds_non_exist_pkg(self, stderr):
        pkg = 'test-pkg'
        expected = "Usage: %s list-builds [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such package: %s\n" % (self.progname, self.progname, pkg)
        self.session.getPackageID.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_builds(self.options, self.session,
                                    ['--package', pkg])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_builds_non_exist_owner(self, stderr):
        owner = 'test-owner'
        expected = "Usage: %s list-builds [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such user: %s\n" % (self.progname, self.progname, owner)
        self.session.getUser.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_builds(self.options, self.session,
                                    ['--owner', owner])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_builds_non_exist_volume(self, stderr):
        volume = 'test-volume'
        expected = "Usage: %s list-builds [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such volume: %s\n" % (self.progname, self.progname, volume)
        self.session.listVolumes.return_value = []
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_builds(self.options, self.session,
                                    ['--volume', volume])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_builds_invalid_state(self, stderr):
        state = '6'
        expected = "Usage: %s list-builds [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Invalid state: %s\n" % (self.progname, self.progname, state)
        self.session.getTag.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_builds(self.options, self.session,
                                    ['--state', state])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_builds_invalid_state_string(self, stderr):
        state = 'test-state'
        expected = "Usage: %s list-builds [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Invalid state: %s\n" % (self.progname, self.progname, state)
        self.session.getTag.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_builds(self.options, self.session,
                                    ['--state', state])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_builds_non_exist_build(self, stderr):
        build = 222
        expected = "Usage: %s list-builds [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such build: '%s'\n" % (self.progname, self.progname, build)
        self.session.getBuild.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_builds(self.options, self.session,
                                    ['--build', build])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_invalid_key(self, stdout, stderr):
        list_build = [{'build_id': 1, 'epoch': 34, 'name': 'test-build',
                       'nvr': 'test-build-11-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 1, 'version': '11'},
                      {'build_id': 4, 'epoch': 34, 'name': 'test-jx-build',
                       'nvr': 'test-jx-build-11-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 1, 'version': '11'},
                      {'build_id': 2, 'epoch': 34, 'name': 'test-ax-build',
                       'nvr': 'test-ax-build-11-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 4, 'version': '11'},
                      {'build_id': 3, 'epoch': 34, 'name': 'test-zx-build',
                       'nvr': 'test-zx-build-11-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 4, 'version': '11'}, ]
        test_key = 'test-key'
        expected_warn = "Invalid sort_key: %s." % test_key
        expected_output = """test-build-11-12                                         kojiadmin         COMPLETE
test-jx-build-11-12                                      kojiadmin         COMPLETE
test-ax-build-11-12                                      kojiadmin         CANCELED
test-zx-build-11-12                                      kojiadmin         CANCELED
"""
        self.session.getUser.return_value = self.user_info
        self.session.listBuilds.return_value = list_build
        rv = anon_handle_list_builds(self.options, self.session, ['--owner', 'kojiadmin',
                                                                  '--sort-key', test_key])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)
        self.assert_console_message(stderr, "%s\n" % expected_warn)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_opt_owner_sorted_nvr(self, stdout):
        list_build = [{'build_id': 1, 'epoch': 34, 'name': 'test-build',
                       'nvr': 'test-build-11-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 1, 'version': '11'},
                      {'build_id': 4, 'epoch': 34, 'name': 'test-jx-build',
                       'nvr': 'test-build-8-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 1, 'version': '8'},
                      {'build_id': 2, 'epoch': 34, 'name': 'test-ax-build',
                       'nvr': 'test-build-11-9', 'owner_name': 'kojiadmin',
                       'release': '9', 'state': 4, 'version': '11'},
                      {'build_id': 3, 'epoch': 34, 'name': 'test-zx-build',
                       'nvr': 'test-build-10-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 4, 'version': '10'}, ]
        expected_output = """test-build-10-12                                         kojiadmin         CANCELED
test-build-11-12                                         kojiadmin         COMPLETE
test-build-11-9                                          kojiadmin         CANCELED
test-build-8-12                                          kojiadmin         COMPLETE
"""
        self.session.getUser.return_value = self.user_info
        self.session.listBuilds.return_value = list_build
        rv = anon_handle_list_builds(self.options, self.session, ['--owner', 'kojiadmin',
                                                                  '--sort-key', 'nvr'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_opt_owner_sorted_state(self, stdout):
        list_build = [{'build_id': 1, 'epoch': 34, 'name': 'test-build',
                       'nvr': 'test-build-11-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 1, 'version': '11'},
                      {'build_id': 4, 'epoch': 34, 'name': 'test-jx-build',
                       'nvr': 'test-build-8-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 1, 'version': '8'},
                      {'build_id': 2, 'epoch': 34, 'name': 'test-ax-build',
                       'nvr': 'test-build-11-9', 'owner_name': 'kojiadmin',
                       'release': '9', 'state': 4, 'version': '11'},
                      {'build_id': 3, 'epoch': 34, 'name': 'test-zx-build',
                       'nvr': 'test-build-10-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 4, 'version': '10'}, ]
        expected_output = """test-build-11-12                                         kojiadmin         COMPLETE
test-build-8-12                                          kojiadmin         COMPLETE
test-build-11-9                                          kojiadmin         CANCELED
test-build-10-12                                         kojiadmin         CANCELED
"""
        self.session.getUser.return_value = self.user_info
        self.session.listBuilds.return_value = list_build
        rv = anon_handle_list_builds(self.options, self.session, ['--owner', 'kojiadmin',
                                                                  '--sort-key', 'state'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_opt_owner_sorted_state_nvr(self, stdout):
        list_build = [{'build_id': 1, 'epoch': 34, 'name': 'test-build',
                       'nvr': 'test-build-11-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 1, 'version': '11'},
                      {'build_id': 4, 'epoch': 34, 'name': 'test-jx-build',
                       'nvr': 'test-build-8-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 1, 'version': '8'},
                      {'build_id': 2, 'epoch': 34, 'name': 'test-ax-build',
                       'nvr': 'test-build-11-9', 'owner_name': 'kojiadmin',
                       'release': '9', 'state': 4, 'version': '11'},
                      {'build_id': 3, 'epoch': 34, 'name': 'test-zx-build',
                       'nvr': 'test-build-10-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 4, 'version': '10'}, ]
        expected_output = """test-build-11-12                                         kojiadmin         COMPLETE
test-build-8-12                                          kojiadmin         COMPLETE
test-build-10-12                                         kojiadmin         CANCELED
test-build-11-9                                          kojiadmin         CANCELED
"""
        self.session.getUser.return_value = self.user_info
        self.session.listBuilds.return_value = list_build
        rv = anon_handle_list_builds(self.options, self.session, ['--owner', 'kojiadmin',
                                                                  '--sort-key', 'state',
                                                                  '--sort-key', 'nvr'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_opt_prefix_sorted_owner(self, stdout):
        list_build = [{'build_id': 1, 'epoch': 34, 'name': 'test-build',
                       'nvr': 'test-build-11-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 1, 'version': '11'},
                      {'build_id': 4, 'epoch': 34, 'name': 'test-jx-build',
                       'nvr': 'test-build-8-12', 'owner_name': 'kojitest',
                       'release': '12', 'state': 1, 'version': '8'},
                      {'build_id': 2, 'epoch': 34, 'name': 'test-ax-build',
                       'nvr': 'test-build-11-9', 'owner_name': 'kojitest',
                       'release': '9', 'state': 4, 'version': '11'},
                      {'build_id': 3, 'epoch': 34, 'name': 'test-zx-build',
                       'nvr': 'test-build-10-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 4, 'version': '10'}, ]
        expected_output = """test-build-11-12                                         kojiadmin         COMPLETE
test-build-10-12                                         kojiadmin         CANCELED
test-build-8-12                                          kojitest          COMPLETE
test-build-11-9                                          kojitest          CANCELED
"""
        self.session.listBuilds.return_value = list_build
        rv = anon_handle_list_builds(self.options, self.session, ['--prefix', 'test-build',
                                                                  '--sort-key', 'owner_name'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_opt_prefix_sorted_owner_nvr(self, stdout):
        list_build = [{'build_id': 1, 'epoch': 34, 'name': 'test-build',
                       'nvr': 'test-build-11-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 1, 'version': '11'},
                      {'build_id': 4, 'epoch': 34, 'name': 'test-jx-build',
                       'nvr': 'test-build-8-12', 'owner_name': 'kojitest',
                       'release': '12', 'state': 1, 'version': '8'},
                      {'build_id': 2, 'epoch': 34, 'name': 'test-ax-build',
                       'nvr': 'test-build-11-9', 'owner_name': 'kojitest',
                       'release': '9', 'state': 4, 'version': '11'},
                      {'build_id': 3, 'epoch': 34, 'name': 'test-zx-build',
                       'nvr': 'test-build-10-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 4, 'version': '10'}, ]
        expected_output = """test-build-10-12                                         kojiadmin         CANCELED
test-build-11-12                                         kojiadmin         COMPLETE
test-build-11-9                                          kojitest          CANCELED
test-build-8-12                                          kojitest          COMPLETE
"""
        self.session.listBuilds.return_value = list_build
        rv = anon_handle_list_builds(self.options, self.session, ['--prefix', 'test-build',
                                                                  '--sort-key', 'owner_name',
                                                                  '--sort-key', 'nvr'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_opt_owner_reverse(self, stdout):
        list_build = [{'build_id': 1, 'epoch': 34, 'name': 'test-build',
                       'nvr': 'test-build-11-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 1, 'version': '11'},
                      {'build_id': 4, 'epoch': 34, 'name': 'test-jx-build',
                       'nvr': 'test-build-8-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 1, 'version': '8'},
                      {'build_id': 2, 'epoch': 34, 'name': 'test-ax-build',
                       'nvr': 'test-build-11-9', 'owner_name': 'kojiadmin',
                       'release': '9', 'state': 4, 'version': '11'},
                      {'build_id': 3, 'epoch': 34, 'name': 'test-zx-build',
                       'nvr': 'test-build-10-12', 'owner_name': 'kojiadmin',
                       'release': '12', 'state': 4, 'version': '10'}, ]
        expected_output = """test-build-8-12                                          kojiadmin         COMPLETE
test-build-11-9                                          kojiadmin         CANCELED
test-build-11-12                                         kojiadmin         COMPLETE
test-build-10-12                                         kojiadmin         CANCELED
"""
        self.session.getUser.return_value = self.user_info
        self.session.listBuilds.return_value = list_build
        rv = anon_handle_list_builds(self.options, self.session, ['--owner', 'kojiadmin',
                                                                  '--reverse'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)
