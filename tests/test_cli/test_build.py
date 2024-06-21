from __future__ import absolute_import
import mock
import six

from koji_cli.commands import handle_build, _progress_callback
from . import utils


class TestBuild(utils.CliTestCase):
    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        # Mock out the options parsed in main
        self.options = mock.MagicMock()
        self.options.quiet = None
        self.options.weburl = 'weburl'
        self.options.poll_interval = 0
        self.options.debug = False
        # Mock out the xmlrpc server
        self.session = mock.MagicMock()
        self.target = 'target'
        self.dest_tag = 'dest_tag'
        self.target_info = {'dest_tag': self.dest_tag}
        self.dest_tag_info = {'locked': False}
        self.source_srpm = 'srpm'
        self.source_scm = 'http://scm'
        self.task_id = 1
        self.priority = None
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.unique_path_mock = mock.patch('koji_cli.commands.unique_path').start()
        self.unique_path_mock.return_value = 'random_path'
        self.running_in_bg_mock = mock.patch('koji_cli.commands._running_in_bg').start()
        self.running_in_bg_mock.return_value = False
        self.watch_tasks_mock = mock.patch('koji_cli.commands.watch_tasks').start()
        self.watch_tasks_mock.return_value = 0
        self.error_format = """Usage: %s build [options] <target> <srpm path or scm url>

The first option is the build target, not to be confused with the destination
tag (where the build eventually lands) or build tag (where the buildroot
contents are pulled from).

You can list all available build targets using the '%s list-targets' command.
More detail can be found in the documentation.
https://docs.pagure.org/koji/HOWTO/#package-organization
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_build_from_srpm(self, stdout):
        args = [self.target, self.source_srpm]
        opts = {'custom_user_metadata': {}, 'wait_builds': []}

        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = self.dest_tag_info
        self.session.build.return_value = self.task_id
        # Run it and check immediate output
        # args: target, srpm
        # expected: success
        rv = handle_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Uploading srpm: srpm

Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_called_once_with(self.dest_tag)
        self.unique_path_mock.assert_called_once_with('cli-build')
        self.assertEqual(self.running_in_bg_mock.call_count, 2)
        self.session.uploadWrapper.assert_called_once_with(
            self.source_srpm, 'random_path', callback=_progress_callback)
        self.session.build.assert_called_once_with(
            'random_path/' + self.source_srpm, self.target, opts, priority=self.priority)
        self.session.logout.assert_called()
        self.watch_tasks_mock.assert_called_once_with(
            self.session, [self.task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval,
            topurl=self.options.topurl)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_build_from_scm(self, stdout):
        args = [self.target, self.source_scm]
        opts = {'custom_user_metadata': {}, 'wait_builds': []}

        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = self.dest_tag_info
        self.session.build.return_value = self.task_id
        # Run it and check immediate output
        # args: target, http://scm
        # expected: success
        rv = handle_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_called_once_with(self.dest_tag)
        self.unique_path_mock.assert_not_called()
        self.running_in_bg_mock.assert_called_once()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_called_once_with(
            self.source_scm, self.target, opts, priority=self.priority)
        self.session.logout.assert_called()
        self.watch_tasks_mock.assert_called_once_with(
            self.session, [self.task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval, topurl=self.options.topurl)
        self.assertEqual(rv, 0)

    def test_handle_build_no_arg(self):
        arguments = []

        # Run it and check immediate output
        self.assert_system_exit(
            handle_build,
            self.options, self.session, arguments,
            stderr=self.format_error_message("Exactly two arguments (a build target and "
                                             "a SCM URL or srpm file) are required"),
            stdout='',
            activate_session=None,
            exit_code=2)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        self.unique_path_mock.assert_not_called()
        self.running_in_bg_mock.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    def test_handle_build_help(self):
        self.assert_help(
            handle_build,
            """Usage: %s build [options] <target> <srpm path or scm url>

The first option is the build target, not to be confused with the destination
tag (where the build eventually lands) or build tag (where the buildroot
contents are pulled from).

You can list all available build targets using the '%s list-targets' command.
More detail can be found in the documentation.
https://docs.pagure.org/koji/HOWTO/#package-organization
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --skip-tag            Do not attempt to tag package
  --scratch             Perform a scratch build
  --rebuild-srpm        Force rebuilding SRPM for scratch build only
  --no-rebuild-srpm     Force not to rebuild srpm for scratch build only
  --wait                Wait on the build, even if running in the background
  --nowait              Don't wait on build
  --wait-repo           Wait for a current repo for the build tag
  --wait-build=NVR      Wait for the given nvr to appear in buildroot repo
  --quiet               Do not print the task information
  --arch-override=ARCH_OVERRIDE
                        Override build arches
  --fail-fast           Override build_arch_can_fail settings and fail as fast
                        as possible
  --repo-id=REPO_ID     Use a specific repo
  --noprogress          Do not display progress of the upload
  --background          Run the build at a lower priority
  --custom-user-metadata=CUSTOM_USER_METADATA
                        Provide a JSON string of custom metadata to be
                        deserialized and stored under the build's
                        extra.custom_user_metadata field
  --draft               Build draft build instead
""" % (self.progname, self.progname))

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        self.unique_path_mock.assert_not_called()
        self.running_in_bg_mock.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_build_custom_user_metadata(self, stdout):
        args = ['--custom-user-metadata={"automation-triggered-by": "yoda"}', self.target,
                self.source_scm]
        opts = {'custom_user_metadata': {'automation-triggered-by': 'yoda'}, 'wait_builds': []}

        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = self.dest_tag_info
        self.session.build.return_value = self.task_id
        # Run it and check immediate output
        # args: target, http://scm
        # expected: success
        rv = handle_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_called_once_with(self.dest_tag)
        self.unique_path_mock.assert_not_called()
        self.running_in_bg_mock.assert_called_once()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_called_once_with(
            self.source_scm, self.target, opts, priority=self.priority)
        self.session.logout.assert_called()
        self.watch_tasks_mock.assert_called_once_with(
            self.session, [self.task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval, topurl=self.options.topurl)
        self.assertEqual(rv, 0)

    def test_handle_build_custom_user_metadata_invalid_json(self):
        arguments = [self.target, self.source_scm,
                     '--custom-user-metadata={Do or do not. There is no try.}']

        # Run it and check immediate output
        self.assert_system_exit(
            handle_build,
            self.options, self.session, arguments,
            stderr=self.format_error_message("--custom-user-metadata is not valid JSON"),
            stdout='',
            activate_session=None,
            exit_code=2)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        self.unique_path_mock.assert_not_called()
        self.running_in_bg_mock.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    def test_handle_build_custom_user_metadata_not_json_object(self):
        arguments = [self.target, self.source_scm,
                     '--custom-user-metadata="Do or do not. There is no try."']

        # Run it and check immediate output
        self.assert_system_exit(
            handle_build,
            self.options, self.session, arguments,
            stderr=self.format_error_message("--custom-user-metadata must be a JSON object"),
            stdout='',
            activate_session=None,
            exit_code=2)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        self.unique_path_mock.assert_not_called()
        self.running_in_bg_mock.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    def test_handle_build_arch_override_denied(self):
        arch_override = 'somearch'
        arguments = [self.target, self.source_scm, '--arch-override=' + arch_override]

        # Run it and check immediate output
        self.assert_system_exit(
            handle_build,
            self.options, self.session, arguments,
            stderr=self.format_error_message(
                "--arch_override is only allowed for --scratch builds"),
            stdout='',
            activate_session=None,
            exit_code=2)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        self.unique_path_mock.assert_not_called()
        self.running_in_bg_mock.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_build_none_tag(self, stdout):
        target = 'nOne'
        repo_id = 2
        args = ['--repo-id=' + str(repo_id), target, self.source_scm]
        opts = {
            'repo_id': repo_id, 'skip_tag': True, 'wait_builds': [], 'custom_user_metadata': {}
        }

        self.session.build.return_value = self.task_id
        # Run it and check immediate output
        # args: --repo-id=2, nOne, http://scm
        # expected: success
        rv = handle_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        self.unique_path_mock.assert_not_called()
        self.running_in_bg_mock.assert_called_once()
        self.session.uploadWrapper.assert_not_called()
        # target==None, repo_id==2, skip_tag==True
        self.session.build.assert_called_once_with(
            self.source_scm, None, opts, priority=self.priority)
        self.session.logout.assert_called()
        self.watch_tasks_mock.assert_called_once_with(
            self.session, [self.task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval, topurl=self.options.topurl)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    def test_handle_build_target_not_found(self, stderr):
        target_info = None
        arguments = [self.target, self.source_scm]

        self.session.getBuildTarget.return_value = target_info
        # Run it and check immediate output
        # args: target, http://scm
        # expected: failed, target not found
        self.assert_system_exit(
            handle_build,
            self.options, self.session, arguments,
            stderr=self.format_error_message("No such build target: target"),
            stdout='',
            activate_session=None,
            exit_code=2)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_not_called()
        self.unique_path_mock.assert_not_called()
        self.running_in_bg_mock.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    def test_handle_build_dest_tag_not_found(self):
        dest_tag_name = 'dest_tag_name'
        target_info = {'dest_tag': self.dest_tag, 'dest_tag_name': dest_tag_name}
        dest_tag_info = None
        arguments = [self.target, self.source_scm]

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        # Run it and check immediate output
        # args: target, http://scm
        # expected: failed, dest_tag not found
        self.assert_system_exit(
            handle_build,
            self.options, self.session, arguments,
            stderr=self.format_error_message("No such destination tag: dest_tag_name"),
            stdout='',
            activate_session=None,
            exit_code=2)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_called_once_with(self.dest_tag)
        self.unique_path_mock.assert_not_called()
        self.running_in_bg_mock.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    def test_handle_build_dest_tag_locked(self):
        dest_tag_name = 'dest_tag_name'
        target_info = {'dest_tag': self.dest_tag, 'dest_tag_name': dest_tag_name}
        dest_tag_info = {'name': 'dest_tag_name', 'locked': True}
        arguments = [self.target, self.source_scm]

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        # Run it and check immediate output
        # args: target, http://scm
        # expected: failed, dest_tag is locked
        self.assert_system_exit(
            handle_build,
            self.options, self.session, arguments,
            stderr=self.format_error_message("Destination tag dest_tag_name is locked"),
            stdout='',
            activate_session=None,
            exit_code=2)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_called_once_with(self.dest_tag)
        self.unique_path_mock.assert_not_called()
        self.running_in_bg_mock.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_build_arch_override(self, stdout):
        arch_override = 'somearch'
        args = ['--arch-override=' + arch_override, '--scratch', self.target, self.source_scm]
        opts = {
            'arch_override': arch_override,
            'custom_user_metadata': {},
            'scratch': True,
            'wait_builds': [],
        }

        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = self.dest_tag_info
        self.session.build.return_value = self.task_id
        # Run it and check immediate output
        # args: --arch-override=somearch, --scratch, target, http://scm
        # expected: success
        rv = handle_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_called_once_with(self.dest_tag)
        self.unique_path_mock.assert_not_called()
        self.running_in_bg_mock.assert_called_once()
        self.session.uploadWrapper.assert_not_called()
        # arch-override=='somearch', scratch==True
        self.session.build.assert_called_once_with(
            self.source_scm, self.target, opts, priority=self.priority)
        self.session.logout.assert_called()
        self.watch_tasks_mock.assert_called_once_with(
            self.session, [self.task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval, topurl=self.options.topurl)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_build_background(self, stdout):
        args = ['--background', self.target, self.source_scm]
        priority = 5
        opts = {'custom_user_metadata': {}, 'wait_builds': []}

        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = self.dest_tag_info
        self.session.build.return_value = self.task_id
        # Run it and check immediate output
        # args: --background, target, http://scm
        # expected: success
        rv = handle_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_called_once_with(self.dest_tag)
        self.unique_path_mock.assert_not_called()
        self.running_in_bg_mock.assert_called_once()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_called_once_with(
            self.source_scm, self.target, opts, priority=priority)
        self.session.logout.assert_called()
        self.watch_tasks_mock.assert_called_once_with(
            self.session, [self.task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval, topurl=self.options.topurl)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands._running_in_bg', return_value=True)
    def test_handle_build_running_in_bg(self, running_in_bg_mock, stdout):
        args = [self.target, self.source_srpm]
        opts = {'custom_user_metadata': {}, 'wait_builds': []}

        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = self.dest_tag_info
        self.session.build.return_value = self.task_id
        # Run it and check immediate output
        # args: target, srpm
        # expected: success
        rv = handle_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Uploading srpm: srpm

Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_called_once_with(self.dest_tag)
        self.unique_path_mock.assert_called_once_with('cli-build')
        self.assertEqual(running_in_bg_mock.call_count, 2)
        # callback==None
        self.session.uploadWrapper.assert_called_once_with(
            self.source_srpm, 'random_path', callback=None)
        self.session.build.assert_called_once_with(
            'random_path/' + self.source_srpm, self.target, opts, priority=self.priority)
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()
        self.assertIsNone(rv)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_build_noprogress(self, stdout):
        args = ['--noprogress', self.target, self.source_srpm]
        opts = {'custom_user_metadata': {}, 'wait_builds': []}

        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = self.dest_tag_info
        self.session.build.return_value = self.task_id
        # Run it and check immediate output
        # args: --noprogress, target, srpm
        # expected: success
        rv = handle_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Uploading srpm: srpm

Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_called_once_with(self.dest_tag)
        self.unique_path_mock.assert_called_once_with('cli-build')
        self.assertEqual(self.running_in_bg_mock.call_count, 2)
        # callback==None
        self.session.uploadWrapper.assert_called_once_with(
            self.source_srpm, 'random_path', callback=None)
        self.session.build.assert_called_once_with(
            'random_path/' + self.source_srpm, self.target, opts, priority=self.priority)
        self.session.logout.assert_called_once()
        self.watch_tasks_mock.assert_called_once_with(
            self.session, [self.task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval, topurl=self.options.topurl)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_build_quiet(self, stdout):
        quiet = True
        args = ['--quiet', self.target, self.source_srpm]
        opts = {'custom_user_metadata': {}, 'wait_builds': []}

        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = self.dest_tag_info
        self.session.build.return_value = self.task_id
        # Run it and check immediate output
        # args: --quiet, target, srpm
        # expected: success
        rv = handle_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = '\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_called_once_with(self.dest_tag)
        self.unique_path_mock.assert_called_once_with('cli-build')
        self.assertEqual(self.running_in_bg_mock.call_count, 2)
        # callback==None
        self.session.uploadWrapper.assert_called_once_with(
            self.source_srpm, 'random_path', callback=None)
        self.session.build.assert_called_once_with(
            'random_path/' + self.source_srpm, self.target, opts, priority=self.priority)
        self.session.logout.assert_called_once()
        self.watch_tasks_mock.assert_called_once_with(
            self.session, [self.task_id], quiet=quiet,
            poll_interval=self.options.poll_interval, topurl=self.options.topurl)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_build_wait(self, stdout):
        args = ['--wait', self.target, self.source_srpm]
        opts = {'custom_user_metadata': {}, 'wait_builds': []}

        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = self.dest_tag_info
        self.session.build.return_value = self.task_id
        # Run it and check immediate output
        # args: --wait, target, srpm
        # expected: success
        rv = handle_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Uploading srpm: srpm

Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_called_once_with(self.dest_tag)
        self.unique_path_mock.assert_called_once_with('cli-build')
        # the second one won't be executed when wait==False
        self.assertEqual(self.running_in_bg_mock.call_count, 1)
        self.session.uploadWrapper.assert_called_once_with(
            self.source_srpm, 'random_path', callback=_progress_callback)
        self.session.build.assert_called_once_with(
            'random_path/' + self.source_srpm, self.target, opts, priority=self.priority)
        self.session.logout.assert_called_once()
        self.watch_tasks_mock.assert_called_once_with(
            self.session, [self.task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval, topurl=self.options.topurl)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_build_nowait(self, stdout):
        args = ['--nowait', self.target, self.source_srpm]
        opts = {'custom_user_metadata': {}, 'wait_builds': []}

        self.session.getBuildTarget.return_value = self.target_info
        self.session.getTag.return_value = self.dest_tag_info
        self.session.build.return_value = self.task_id
        # Run it and check immediate output
        # args: --nowait, target, srpm
        # expected: success
        rv = handle_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Uploading srpm: srpm

Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_called_once_with(self.dest_tag)
        self.unique_path_mock.assert_called_once_with('cli-build')
        # the second one won't be executed when wait==False
        self.assertEqual(self.running_in_bg_mock.call_count, 1)
        self.session.uploadWrapper.assert_called_once_with(
            self.source_srpm, 'random_path', callback=_progress_callback)
        self.session.build.assert_called_once_with(
            'random_path/' + self.source_srpm, self.target, opts, priority=self.priority)
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()
        self.assertIsNone(rv)

    def test_handle_build_rebuild_srpm_without_scratch(self):
        arguments = ['--rebuild-srpm', self.target, self.source_srpm]

        # Run it and check immediate output
        self.assert_system_exit(
            handle_build,
            self.options, self.session, arguments,
            stderr=self.format_error_message(
                "--no-/rebuild-srpm is only allowed for --scratch builds"),
            stdout='',
            activate_session=None,
            exit_code=2)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        self.unique_path_mock.assert_not_called()
        self.running_in_bg_mock.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()
