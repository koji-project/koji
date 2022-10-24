from __future__ import absolute_import
import koji
import mock
import os
import time
import copy
import locale
from six.moves import StringIO

from koji_cli.commands import anon_handle_buildinfo
from . import utils


class TestBuildinfo(utils.CliTestCase):
    def setUp(self):
        # force locale to compare 'expect' value
        locale.setlocale(locale.LC_ALL, ('en_US', 'UTF-8'))
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.quiet = True
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.error_format = """Usage: %s buildinfo [options] <n-v-r> [<n-v-r> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.original_timezone = os.environ.get('TZ')
        os.environ['TZ'] = 'UTC'
        time.tzset()
        self.taskinfo = {'arch': 'noarch',
                         'id': 8,
                         'method': 'build',
                         'request': ['src', 'target', 'opts']}
        self.buildinfo = {'build_id': 1,
                          'id': 1,
                          'name': 'test-build',
                          'release': '1',
                          'task_id': 8,
                          'version': '1',
                          'state': 1,
                          'completion_ts': 1614869140.368759,
                          'owner_name': 'kojiadmin',
                          'volume_name': 'DEFAULT'}

    def tearDown(self):
        locale.setlocale(locale.LC_ALL, "")
        if self.original_timezone is None:
            del os.environ['TZ']
        else:
            os.environ['TZ'] = self.original_timezone
        time.tzset()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_buildinfo_valid(self, stdout):
        build = 'test-build-1-1'
        self.session.getBuild.return_value = self.buildinfo
        self.session.getTaskInfo.return_value = self.taskinfo
        self.session.listTags.return_value = []
        self.session.getMavenBuild.return_value = None
        self.session.getWinBuild.return_value = None
        self.session.listArchives.return_value = []
        self.session.listRPMs.return_value = []
        expected_stdout = """BUILD: test-build-1-1 [1]
State: COMPLETE
Built by: kojiadmin
Volume: DEFAULT
Task: 8 build (target, src)
Finished: Thu, 04 Mar 2021 14:45:40 UTC
Tags: 
"""
        anon_handle_buildinfo(self.options, self.session, [build])
        self.assert_console_message(stdout, expected_stdout)
        self.session.listTags.assert_called_once_with(build)
        self.session.getBuild.assert_called_once_with(build)
        self.session.getTaskInfo.assert_called_once_with(self.buildinfo['task_id'], request=True)
        self.session.getMavenBuild.assert_called_once_with(self.buildinfo['id'])
        self.session.getWinBuild.assert_called_once_with(self.buildinfo['id'])
        self.session.listRPMs.assert_called_once_with(buildID=self.buildinfo['id'])
        self.assertEqual(self.session.listArchives.call_count, 4)

    def test_buildinfo_more_build_with_non_exist_build(self):
        build = 'test-build-1-1'
        non_exist_build = 'test-build-11-12'
        buildinfo = copy.deepcopy(self.buildinfo)
        buildinfo['task_id'] = None
        self.session.getBuild.side_effect = [None, buildinfo]
        self.session.listTags.return_value = []
        self.session.getMavenBuild.return_value = None
        self.session.getWinBuild.return_value = None
        self.session.listArchives.return_value = []
        self.session.listRPMs.return_value = []
        expected_stdout = """BUILD: test-build-1-1 [1]
State: COMPLETE
Built by: kojiadmin
Volume: DEFAULT
Task: none
Finished: Thu, 04 Mar 2021 14:45:40 UTC
Tags: 
"""
        arguments = [non_exist_build, build]
        self.assert_system_exit(
            anon_handle_buildinfo,
            self.options, self.session, arguments,
            stderr="No such build: %s\n\n" % non_exist_build,
            stdout=expected_stdout,
            activate_session=None,
            exit_code=1)
        self.session.listTags.assert_called_once_with(build)
        self.session.getMavenBuild.assert_called_once_with(self.buildinfo['id'])
        self.session.getWinBuild.assert_called_once_with(self.buildinfo['id'])
        self.session.listRPMs.assert_called_once_with(buildID=self.buildinfo['id'])
        self.assertEqual(self.session.getBuild.call_count, 2)
        self.assertEqual(self.session.listArchives.call_count, 4)

    def test_buildinfo_non_exist_build(self):
        non_exist_build = 'test-build-11-12'
        self.session.getBuild.return_value = None
        arguments = [non_exist_build]
        self.assert_system_exit(
            anon_handle_buildinfo,
            self.options, self.session, arguments,
            stderr="No such build: %s\n\n" % non_exist_build,
            stdout='',
            activate_session=None,
            exit_code=1)

    def test_buildinfo_without_option(self):
        arguments = []
        self.assert_system_exit(
            anon_handle_buildinfo,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("Please specify a build"),
            exit_code=2,
            activate_session=None)
        self.session.listTags.assert_not_called()
        self.session.getMavenBuild.assert_not_called()
        self.session.getWinBuild.assert_not_called()
        self.session.listRPMs.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_buildinfo_valid_win_maven_image_with_changelog(self, stdout):
        build_id = 1
        build_info = self.buildinfo.copy()
        build_info['state'] = 0
        build_info['source'] = 'test-source'
        build_info['cg_name'] = 'cg-name-test'
        build_info['extra'] = {'test-extra': 'result-extra'}
        list_all_archives = [{'id': 987, 'filename': 'test-maven-file', 'group_id': '222',
                              'artifact_id': '555', 'version': '2'},
                             {'id': 988, 'filename': 'test-win-file', 'relpath': 'test-rel-path'},
                             {'id': 989, 'filename': 'test-image-filename'},
                             {'id': 990, 'filename': 'test-extra-filename', 'btype': 'test-btype'}]
        self.session.getBuild.return_value = build_info
        self.session.getTaskInfo.return_value = self.taskinfo
        self.session.listTags.return_value = [{'id': 123, 'name': 'test-tag'}]
        self.session.getMavenBuild.return_value = {
            'build_id': 12345, 'group_id': 222, 'artifact_id': 555, 'version': 2}
        self.session.getWinBuild.return_value = {'build_id': 12346, 'platform': 'test-platform'}
        self.session.listArchives.side_effect = [
            [list_all_archives[0]], [list_all_archives[1]], [list_all_archives[2]],
            list_all_archives]
        self.session.listRPMs.return_value = []
        self.session.getChangelogEntries.return_value = {'author': 'Test user',
                                                         'date': '2022-10-03 12:00:00',
                                                         'date_ts': 1664798400,
                                                         'text': '- change for test'},
        expected_stdout = """BUILD: test-build-1-1 [1]
State: BUILDING
Reserved by: cg-name-test
Built by: kojiadmin
Source: test-source
Volume: DEFAULT
Task: 8 build (target, src)
Finished: Thu, 04 Mar 2021 14:45:40 UTC
Maven groupId: 222
Maven artifactId: 555
Maven version: 2
Windows build platform: test-platform
Tags: test-tag
Extra: {'test-extra': 'result-extra'}
Maven archives:
/mnt/koji/packages/test-build/1/1/maven/222/555/2/test-maven-file
Windows archives:
/mnt/koji/packages/test-build/1/1/win/test-rel-path/test-win-file
Image archives:
/mnt/koji/packages/test-build/1/1/images/test-image-filename
Test-btype Archives:
/mnt/koji/packages/test-build/1/1/files/test-btype/test-extra-filename
Changelog:
* Mon Oct 03 2022 Test user
- change for test


"""
        anon_handle_buildinfo(self.options, self.session, [str(build_id), '--changelog'])
        self.assert_console_message(stdout, expected_stdout)
        self.session.listTags.assert_called_once_with(build_id)
        self.session.getBuild.assert_called_once_with(build_id)
        self.session.getTaskInfo.assert_called_once_with(self.buildinfo['task_id'], request=True)
        self.session.getMavenBuild.assert_called_once_with(self.buildinfo['id'])
        self.session.getWinBuild.assert_called_once_with(self.buildinfo['id'])
        self.session.listRPMs.assert_called_once_with(buildID=self.buildinfo['id'])
        self.assertEqual(self.session.listArchives.call_count, 4)
