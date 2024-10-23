from __future__ import absolute_import

try:
    from unittest import mock
except ImportError:
    import mock
import os
import time
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
        self.ensure_connection_mock = mock.patch('koji_cli.commands.ensure_connection').start()
        self.original_timezone = os.environ.get('TZ')
        os.environ['TZ'] = 'UTC'
        time.tzset()
        self.user_info = {'id': 1, 'name': 'kojiadmin', 'status': 0, 'usertype': 0,
                          'krb_principals': []}
        self.owner = 'kojiadmin'
        self.error_format = """Usage: %s list-builds [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.list_build = [
            {'build_id': 1, 'epoch': 34, 'name': 'test-build', 'volume_id': 1,
             'nvr': 'test-build-11-12', 'owner_name': 'kojiadmin', 'task_id': None,
             'release': '12', 'state': 1, 'version': '11', 'package_id': 1,
             'source': 'test-source-1', 'completion_time': '2023-02-03 14:35'},
            {'build_id': 4, 'epoch': 34, 'name': 'test-build', 'volume_id': 0,
             'nvr': 'test-build-8-12', 'owner_name': 'kojiadmin', 'task_id': 40,
             'release': '12', 'state': 2, 'version': '8', 'package_id': 1,
             'source': 'test-source-2', 'completion_time': '2023-02-01 14:35'},
            {'build_id': 2, 'epoch': 34, 'name': 'test-build', 'volume_id': 0,
             'nvr': 'test-build-11-9', 'owner_name': 'kojitest', 'task_id': 20,
             'release': '9', 'state': 1, 'version': '11', 'package_id': 1,
             'source': 'test-source-3', 'completion_time': '2023-01-03 14:35'},
            {'build_id': 3, 'epoch': 34, 'name': 'test-build', 'volume_id': 0,
             'nvr': 'test-build-10-12', 'owner_name': 'kojitest', 'task_id': None,
             'release': '12', 'state': 4, 'version': '10', 'package_id': 1,
             'source': 'test-source-4', 'completion_time': '2023-02-08 14:35'},
            {'build_id': 5, 'epoch': 34, 'name': 'test-zx-build', 'volume_id': 1,
             'nvr': 'build-test-1-12', 'owner_name': 'kojiadmin', 'task_id': 50,
             'release': '12', 'state': 4, 'version': '1', 'package_id': 2,
             'source': 'test-source-5', 'completion_time': '2023-02-04 14:35'}]

    def tearDown(self):
        mock.patch.stopall()
        if self.original_timezone is None:
            del os.environ['TZ']
        else:
            os.environ['TZ'] = self.original_timezone
        time.tzset()

    def test_list_buildroot_with_args(self):
        self.assert_system_exit(
            anon_handle_list_builds,
            self.options, self.session, ['arg'],
            stderr=self.format_error_message('This command takes no arguments'),
            exit_code=2,
            activate_session=None)
        self.ensure_connection_mock.assert_not_called()
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_not_called()

    def test_list_builds_without_option(self):
        self.assert_system_exit(
            anon_handle_list_builds,
            self.options, self.session, [],
            stderr=self.format_error_message('Filter must be provided for list'),
            exit_code=2,
            activate_session=None)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_not_called()

    def test_list_builds_non_exist_pkg(self):
        pkg = 'test-pkg'
        self.session.getPackageID.return_value = None
        self.assert_system_exit(
            anon_handle_list_builds,
            self.options, self.session, ['--package', pkg],
            stderr=self.format_error_message('No such package: %s' % pkg),
            exit_code=2,
            activate_session=None)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_called_once_with(pkg)
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_not_called()

    def test_list_builds_non_exist_owner(self):
        owner = 'test-owner'
        self.session.getUser.return_value = None
        self.assert_system_exit(
            anon_handle_list_builds,
            self.options, self.session, ['--owner', owner],
            stderr=self.format_error_message('No such user: %s' % owner),
            exit_code=2,
            activate_session=None)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_called_once_with(owner)
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_not_called()

    def test_list_builds_non_exist_volume(self):
        volume = 'test-volume'
        self.session.listVolumes.return_value = []
        self.assert_system_exit(
            anon_handle_list_builds,
            self.options, self.session, ['--volume', volume],
            stderr=self.format_error_message('No such volume: %s' % volume),
            exit_code=2,
            activate_session=None)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_called_once_with()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_not_called()

    def test_list_builds_invalid_state(self):
        state = '6'
        self.assert_system_exit(
            anon_handle_list_builds,
            self.options, self.session, ['--state', state],
            stderr=self.format_error_message('Invalid state: %s' % state),
            exit_code=2,
            activate_session=None)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_not_called()

    def test_list_builds_invalid_state_string(self):
        state = 'test-state'
        self.assert_system_exit(
            anon_handle_list_builds,
            self.options, self.session, ['--state', state],
            stderr=self.format_error_message('Invalid state: %s' % state),
            exit_code=2,
            activate_session=None)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_not_called()

    def test_list_builds_non_exist_build(self):
        build = 222
        self.session.getBuild.return_value = None
        self.assert_system_exit(
            anon_handle_list_builds,
            self.options, self.session, ['--build', build],
            stderr=self.format_error_message("No such build: '%s'" % build),
            exit_code=2,
            activate_session=None)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_called_once_with(build)
        self.session.listBuilds.assert_not_called()

    @mock.patch('sys.stderr', new_callable=StringIO)
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_invalid_key(self, stdout, stderr):
        test_key = 'test-key'
        expected_warn = "Invalid sort_key: %s." % test_key
        expected_output = """test-build-11-12                                         kojiadmin         COMPLETE
test-build-8-12                                          kojiadmin         DELETED
build-test-1-12                                          kojiadmin         CANCELED
"""
        self.session.getUser.return_value = self.user_info
        self.session.listBuilds.return_value = [self.list_build[0], self.list_build[1],
                                                self.list_build[4]]
        rv = anon_handle_list_builds(self.options, self.session, ['--owner', self.owner,
                                                                  '--sort-key', test_key])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)
        self.assert_console_message(stderr, "%s\n" % expected_warn)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_called_once_with(self.owner)
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(userID=1)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_opt_owner_sorted_nvr(self, stdout):
        expected_output = """build-test-1-12                                          kojiadmin         CANCELED
test-build-11-12                                         kojiadmin         COMPLETE
test-build-8-12                                          kojiadmin         DELETED
"""
        self.session.getUser.return_value = self.user_info
        self.session.listBuilds.return_value = [self.list_build[0], self.list_build[1],
                                                self.list_build[4]]
        rv = anon_handle_list_builds(self.options, self.session, ['--owner', self.owner,
                                                                  '--sort-key', 'nvr'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_called_once_with(self.owner)
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(userID=1)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_opt_before(self, stdout):
        expected_output = """test-build-11-9                                          kojitest          COMPLETE
test-build-8-12                                          kojiadmin         DELETED
"""
        self.session.getUser.return_value = self.user_info
        self.session.listBuilds.return_value = [self.list_build[1], self.list_build[2]]
        rv = anon_handle_list_builds(self.options, self.session, ['--before', "2023-02-01 23:59",
                                                                  '--sort-key', 'nvr'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(completeBefore=1675295940.0)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_opt_after(self, stdout):
        expected_output = """build-test-1-12                                          kojiadmin         CANCELED
test-build-10-12                                         kojitest          CANCELED
test-build-11-12                                         kojiadmin         COMPLETE
"""
        self.session.getUser.return_value = self.user_info
        self.session.listBuilds.return_value = [self.list_build[0], self.list_build[3],
                                                self.list_build[4]]
        rv = anon_handle_list_builds(self.options, self.session, ['--after', "2023-02-01 23:59",
                                                                  '--sort-key', 'nvr'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(completeAfter=1675295940.0)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_opt_owner_sorted_state(self, stdout):
        expected_output = """test-build-11-12                                         kojiadmin         COMPLETE
test-build-8-12                                          kojiadmin         DELETED
build-test-1-12                                          kojiadmin         CANCELED
"""
        self.session.getUser.return_value = self.user_info
        self.session.listBuilds.return_value = [self.list_build[0], self.list_build[1],
                                                self.list_build[4]]
        rv = anon_handle_list_builds(self.options, self.session, ['--owner', self.owner,
                                                                  '--sort-key', 'state'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_called_once_with(self.owner)
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(userID=1)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_opt_owner_sorted_state_nvr(self, stdout):
        expected_output = """test-build-11-12                                         kojiadmin         COMPLETE
test-build-8-12                                          kojiadmin         DELETED
build-test-1-12                                          kojiadmin         CANCELED
"""
        self.session.getUser.return_value = self.user_info
        self.session.listBuilds.return_value = [self.list_build[0], self.list_build[1],
                                                self.list_build[4]]
        rv = anon_handle_list_builds(self.options, self.session, ['--owner', self.owner,
                                                                  '--sort-key', 'state',
                                                                  '--sort-key', 'nvr'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_called_once_with(self.owner)
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(userID=1)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_opt_prefix_sorted_owner(self, stdout):
        expected_output = """test-build-11-12                                         kojiadmin         COMPLETE
test-build-8-12                                          kojiadmin         DELETED
build-test-1-12                                          kojiadmin         CANCELED
test-build-11-9                                          kojitest          COMPLETE
test-build-10-12                                         kojitest          CANCELED
"""
        self.session.listBuilds.return_value = self.list_build
        rv = anon_handle_list_builds(self.options, self.session, ['--prefix', 'test-build',
                                                                  '--sort-key', 'owner_name'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(prefix='test-build')

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_opt_prefix_sorted_owner_nvr(self, stdout):
        expected_output = """build-test-1-12                                          kojiadmin         CANCELED
test-build-11-12                                         kojiadmin         COMPLETE
test-build-8-12                                          kojiadmin         DELETED
test-build-10-12                                         kojitest          CANCELED
test-build-11-9                                          kojitest          COMPLETE
"""
        self.session.listBuilds.return_value = self.list_build
        rv = anon_handle_list_builds(self.options, self.session, ['--prefix', 'test-build',
                                                                  '--sort-key', 'owner_name',
                                                                  '--sort-key', 'nvr'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(prefix='test-build')

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_opt_owner_reverse(self, stdout):
        expected_output = """build-test-1-12                                          kojiadmin         CANCELED
test-build-8-12                                          kojiadmin         DELETED
test-build-11-12                                         kojiadmin         COMPLETE
"""
        self.session.getUser.return_value = self.user_info
        self.session.listBuilds.return_value = [self.list_build[0], self.list_build[1],
                                                self.list_build[4]]
        rv = anon_handle_list_builds(self.options, self.session, ['--owner', self.owner,
                                                                  '--reverse'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_called_once_with(self.owner)
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(userID=1)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_opt_cg(self, stdout):
        expected_output = """test-build-11-9                                          kojitest          COMPLETE
test-build-8-12                                          kojiadmin         DELETED
"""
        self.session.listBuilds.return_value = [self.list_build[1], self.list_build[2]]
        rv = anon_handle_list_builds(self.options, self.session, ['--cg', 'test-cg'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(cgID='test-cg')

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_pkg_not_int(self, stdout):
        pkg = 'build-test'
        expected_output = """build-test-1-12                                          kojiadmin         CANCELED
"""
        self.session.getPackageID.return_value = 2
        self.session.listBuilds.return_value = [self.list_build[4]]
        rv = anon_handle_list_builds(self.options, self.session, ['--package', pkg])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_called_once_with(pkg)
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(packageID=2)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_pkg_int(self, stdout):
        pkg = 2
        expected_output = """build-test-1-12                                          kojiadmin         CANCELED
"""
        self.session.listBuilds.return_value = [self.list_build[4]]
        rv = anon_handle_list_builds(self.options, self.session, ['--package', str(pkg)])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(packageID=2)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_volume_not_int(self, stdout):
        volume = 'test-volume'
        expected_output = """test-build-11-12                                         kojiadmin         COMPLETE
build-test-1-12                                          kojiadmin         CANCELED
"""
        self.session.listBuilds.return_value = [self.list_build[0], self.list_build[4]]
        self.session.listVolumes.return_value = [{'id': 0, 'name': 'DEFAULT'},
                                                 {'id': 1, 'name': 'test-volume'}]
        rv = anon_handle_list_builds(self.options, self.session, ['--volume', volume])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_called_once_with()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(volumeID=1)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_volume_int(self, stdout):
        volume = 1
        expected_output = """test-build-11-12                                         kojiadmin         COMPLETE
build-test-1-12                                          kojiadmin         CANCELED
"""
        self.session.listBuilds.return_value = [self.list_build[0], self.list_build[4]]
        rv = anon_handle_list_builds(self.options, self.session, ['--volume', volume])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(volumeID=1)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_state(self, stdout):
        expected_output = """test-build-8-12                                          kojiadmin         DELETED
"""
        self.session.listBuilds.return_value = [self.list_build[1]]
        rv = anon_handle_list_builds(self.options, self.session, ['--state', '2'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(state=2)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_task_int(self, stdout):
        expected_output = """test-build-11-9                                          kojitest          COMPLETE
"""
        self.session.listBuilds.return_value = [self.list_build[2]]
        rv = anon_handle_list_builds(self.options, self.session, ['--task', '20'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(taskID=20)

    def test_list_builds_task_not_int(self):
        self.assert_system_exit(
            anon_handle_list_builds,
            self.options, self.session, ['--task', 'task-id'],
            stderr=self.format_error_message("Task id must be an integer"),
            exit_code=2,
            activate_session=None)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_build_string(self, stdout):
        expected_output = """test-build-11-9                                          kojitest          COMPLETE
"""
        self.session.getBuild.return_value = self.list_build[2]
        rv = anon_handle_list_builds(self.options, self.session, ['--buildid', 'test-build-10-12'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_called_once_with('test-build-10-12')
        self.session.listBuilds.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_builds_build_source_without_quiet(self, stdout):
        self.options.quiet = False
        expected_output = """Build                                                    Built by          State
-------------------------------------------------------  ----------------  ----------------
test-build-10-12                                         kojitest          CANCELED
"""
        self.session.listBuilds.return_value = [self.list_build[3]]
        rv = anon_handle_list_builds(self.options, self.session, ['--source', 'test-source-4'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected_output)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(source='test-source-4')

    def test_list_builds_pattern_option_error(self):
        self.session.listBuilds.side_effect = koji.ParameterError("no option 'pattern'")
        expected = "The hub doesn't support the 'pattern' argument, please try filtering " \
                   "the result on your local instead."
        self.assert_system_exit(
            anon_handle_list_builds,
            self.options, self.session, ['--pattern', 'pattern'],
            stderr=self.format_error_message(expected),
            exit_code=2,
            activate_session=None)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(pattern='pattern')

    def test_list_builds_cgid_option_error(self):
        self.session.listBuilds.side_effect = koji.ParameterError("no option 'cgID'")
        expected = "The hub doesn't support the 'cg' argument, please try filtering " \
                   "the result on your local instead."
        self.assert_system_exit(
            anon_handle_list_builds,
            self.options, self.session, ['--cg', 'test-cg'],
            stderr=self.format_error_message(expected),
            exit_code=2,
            activate_session=None)

        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.getPackageID.assert_not_called()
        self.session.getUser.assert_not_called()
        self.session.listVolumes.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.listBuilds.assert_called_once_with(cgID='test-cg')

    def test_list_builds_help(self):
        self.assert_help(
            anon_handle_list_builds,
            """Usage: %s list-builds [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --package=PACKAGE     List builds for this package
  --buildid=BUILDID     List specific build from ID or nvr
  --before=BEFORE       List builds built before this time, time is specified
                        as timestamp or date/time in any format which can be
                        parsed by dateutil.parser. e.g. "2020-12-31 12:35" or
                        "December 31st 12:35"
  --after=AFTER         List builds built after this time (same format as for
                        --before
  --state=STATE         List builds in this state
  --task=TASK           List builds for this task
  --type=TYPE           List builds of this type.
  --prefix=PREFIX       Only builds starting with this prefix
  --pattern=PATTERN     Only list builds matching this GLOB pattern
  --cg=CG               Only list builds imported by matching content
                        generator name
  --source=SOURCE       Only builds where the source field matches (glob
                        pattern)
  --owner=OWNER         List builds built by this owner
  --volume=VOLUME       List builds by volume ID
  --draft-only          Only list draft builds
  --no-draft            Only list regular builds
  -k FIELD, --sort-key=FIELD
                        Sort the list by the named field. Allowed sort keys:
                        build_id, owner_name, state
  -r, --reverse         Print the list in reverse order
  --quiet               Do not print the header information
""" % self.progname)
