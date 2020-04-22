from __future__ import absolute_import
import mock
import os
import six
import sys

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
        # Mock out the xmlrpc server
        self.session = mock.MagicMock()
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

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.unique_path', return_value='random_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_from_srpm(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            unique_path_mock,
            activate_session_mock,
            stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        target_info = {'dest_tag': dest_tag}
        dest_tag_info = {'locked': False}
        source = 'srpm'
        task_id = 1
        args = [target, source]
        opts = {'wait_builds': []}
        priority = None

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.build.return_value = task_id
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
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag)
        unique_path_mock.assert_called_once_with('cli-build')
        self.assertEqual(running_in_bg_mock.call_count, 2)
        self.session.uploadWrapper.assert_called_once_with(
            source, 'random_path', callback=_progress_callback)
        self.session.build.assert_called_once_with(
            'random_path/' + source, target, opts, priority=priority)
        self.session.logout.assert_called()
        watch_tasks_mock.assert_called_once_with(
            self.session, [task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.unique_path', return_value='random_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_from_scm(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            unique_path_mock,
            activate_session_mock,
            stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        target_info = {'dest_tag': dest_tag}
        dest_tag_info = {'locked': False}
        source = 'http://scm'
        task_id = 1
        args = [target, source]
        opts = {'wait_builds': []}
        priority = None

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.build.return_value = task_id
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
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag)
        unique_path_mock.assert_not_called()
        running_in_bg_mock.assert_called_once()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_called_once_with(
            source, target, opts, priority=priority)
        self.session.logout.assert_called()
        watch_tasks_mock.assert_called_once_with(
            self.session, [task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.unique_path', return_value='random_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_no_arg(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            unique_path_mock,
            activate_session_mock,
            stderr,
            stdout):
        args = []
        progname = os.path.basename(sys.argv[0]) or 'koji'

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            handle_build(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = ''
        expected_stderr = self.format_error_message("Exactly two arguments (a build target and a SCM URL or srpm file) are required")
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        unique_path_mock.assert_not_called()
        running_in_bg_mock.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_not_called()
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.unique_path', return_value='random_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_help(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            unique_path_mock,
            activate_session_mock,
            stderr,
            stdout):
        args = ['--help']
        progname = os.path.basename(sys.argv[0]) or 'koji'

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            handle_build(self.options, self.session, args)
        self.assertExitCode(ex, 0)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = """Usage: %s build [options] <target> <srpm path or scm url>

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
  --wait-repo           Wait for the actual buildroot repo of given target
  --wait-build=NVR      Wait for the given nvr to appear in buildroot repo
  --quiet               Do not print the task information
  --arch-override=ARCH_OVERRIDE
                        Override build arches
  --fail-fast           Override build_arch_can_fail settings and fail as fast
                        as possible
  --repo-id=REPO_ID     Use a specific repo
  --noprogress          Do not display progress of the upload
  --background          Run the build at a lower priority
""" % (progname, progname)
        expected_stderr = ''
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        unique_path_mock.assert_not_called()
        running_in_bg_mock.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_not_called()
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.unique_path', return_value='random_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_arch_override_denied(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            unique_path_mock,
            activate_session_mock,
            stderr,
            stdout):
        target = 'target'
        source = 'http://scm'
        arch_override = 'somearch'
        args = [target, source, '--arch-override=' + arch_override]
        progname = os.path.basename(sys.argv[0]) or 'koji'

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            handle_build(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = ''
        expected_stderr = self.format_error_message("--arch_override is only allowed for --scratch builds")
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        unique_path_mock.assert_not_called()
        running_in_bg_mock.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_not_called()
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.unique_path', return_value='random_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_none_tag(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            unique_path_mock,
            activate_session_mock,
            stdout):
        target = 'nOne'
        source = 'http://scm'
        task_id = 1
        repo_id = 2
        args = ['--repo-id=' + str(repo_id), target, source]
        opts = {'repo_id': repo_id, 'skip_tag': True, 'wait_builds': []}
        priority = None

        self.session.build.return_value = task_id
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
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        unique_path_mock.assert_not_called()
        running_in_bg_mock.assert_called_once()
        self.session.uploadWrapper.assert_not_called()
        # target==None, repo_id==2, skip_tag==True
        self.session.build.assert_called_once_with(
            source, None, opts, priority=priority)
        self.session.logout.assert_called()
        watch_tasks_mock.assert_called_once_with(
            self.session, [task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.unique_path', return_value='random_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_target_not_found(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            unique_path_mock,
            activate_session_mock,
            stderr):
        target = 'target'
        target_info = None
        source = 'http://scm'
        args = [target, source]

        progname = os.path.basename(sys.argv[0]) or 'koji'

        self.session.getBuildTarget.return_value = target_info
        # Run it and check immediate output
        # args: target, http://scm
        # expected: failed, target not found
        with self.assertRaises(SystemExit) as ex:
            handle_build(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        actual = stderr.getvalue()
        expected = self.format_error_message( "Unknown build target: target")
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_not_called()
        unique_path_mock.assert_not_called()
        running_in_bg_mock.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_not_called()
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.unique_path', return_value='random_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_dest_tag_not_found(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            unique_path_mock,
            activate_session_mock,
            stderr):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_name = 'dest_tag_name'
        target_info = {'dest_tag': dest_tag, 'dest_tag_name': dest_tag_name}
        dest_tag_info = None
        source = 'http://scm'
        args = [target, source]

        progname = os.path.basename(sys.argv[0]) or 'koji'

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        # Run it and check immediate output
        # args: target, http://scm
        # expected: failed, dest_tag not found
        with self.assertRaises(SystemExit) as ex:
            handle_build(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        actual = stderr.getvalue()
        expected = self.format_error_message("Unknown destination tag: dest_tag_name")
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag)
        unique_path_mock.assert_not_called()
        running_in_bg_mock.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_not_called()
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.unique_path', return_value='random_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_dest_tag_locked(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            unique_path_mock,
            activate_session_mock,
            stderr):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_name = 'dest_tag_name'
        target_info = {'dest_tag': dest_tag, 'dest_tag_name': dest_tag_name}
        dest_tag_info = {'name': 'dest_tag_name', 'locked': True}
        source = 'http://scm'
        args = [target, source]

        progname = os.path.basename(sys.argv[0]) or 'koji'

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        # Run it and check immediate output
        # args: target, http://scm
        # expected: failed, dest_tag is locked
        with self.assertRaises(SystemExit) as ex:
            handle_build(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        actual = stderr.getvalue()
        expected = self.format_error_message("Destination tag dest_tag_name is locked")
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag)
        unique_path_mock.assert_not_called()
        running_in_bg_mock.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_not_called()
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.unique_path', return_value='random_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_arch_override(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            unique_path_mock,
            activate_session_mock,
            stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        target_info = {'dest_tag': dest_tag}
        dest_tag_info = {'locked': False}
        source = 'http://scm'
        task_id = 1
        arch_override = 'somearch'
        args = [
            '--arch-override=' +
            arch_override,
            '--scratch',
            target,
            source]
        opts = {'arch_override': arch_override, 'scratch': True, 'wait_builds': []}
        priority = None

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.build.return_value = task_id
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
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag)
        unique_path_mock.assert_not_called()
        running_in_bg_mock.assert_called_once()
        self.session.uploadWrapper.assert_not_called()
        # arch-override=='somearch', scratch==True
        self.session.build.assert_called_once_with(
            source, target, opts, priority=priority)
        self.session.logout.assert_called()
        watch_tasks_mock.assert_called_once_with(
            self.session, [task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.unique_path', return_value='random_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_background(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            unique_path_mock,
            activate_session_mock,
            stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        target_info = {'dest_tag': dest_tag}
        dest_tag_info = {'locked': False}
        source = 'http://scm'
        task_id = 1
        args = ['--background', target, source]
        priority = 5
        opts = {'wait_builds': []}

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.build.return_value = task_id
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
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag)
        unique_path_mock.assert_not_called()
        running_in_bg_mock.assert_called_once()
        self.session.uploadWrapper.assert_not_called()
        self.session.build.assert_called_once_with(
            source, target, opts, priority=priority)
        self.session.logout.assert_called()
        watch_tasks_mock.assert_called_once_with(
            self.session, [task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.unique_path', return_value='random_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=True)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_running_in_bg(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            unique_path_mock,
            activate_session_mock,
            stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        target_info = {'dest_tag': dest_tag}
        dest_tag_info = {'locked': False}
        source = 'srpm'
        task_id = 1
        args = [target, source]
        opts = {'wait_builds': []}
        priority = None

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.build.return_value = task_id
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
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag)
        unique_path_mock.assert_called_once_with('cli-build')
        self.assertEqual(running_in_bg_mock.call_count, 2)
        # callback==None
        self.session.uploadWrapper.assert_called_once_with(
            source, 'random_path', callback=None)
        self.session.build.assert_called_once_with(
            'random_path/' + source, target, opts, priority=priority)
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()
        self.assertIsNone(rv)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.unique_path', return_value='random_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_noprogress(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            unique_path_mock,
            activate_session_mock,
            stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        target_info = {'dest_tag': dest_tag}
        dest_tag_info = {'locked': False}
        source = 'srpm'
        task_id = 1
        args = ['--noprogress', target, source]
        opts = {'wait_builds': []}
        priority = None

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.build.return_value = task_id
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
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag)
        unique_path_mock.assert_called_once_with('cli-build')
        self.assertEqual(running_in_bg_mock.call_count, 2)
        # callback==None
        self.session.uploadWrapper.assert_called_once_with(
            source, 'random_path', callback=None)
        self.session.build.assert_called_once_with(
            'random_path/' + source, target, opts, priority=priority)
        self.session.logout.assert_called_once()
        watch_tasks_mock.assert_called_once_with(
            self.session, [task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.unique_path', return_value='random_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_quiet(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            unique_path_mock,
            activate_session_mock,
            stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        target_info = {'dest_tag': dest_tag}
        dest_tag_info = {'locked': False}
        source = 'srpm'
        task_id = 1
        quiet = True
        args = ['--quiet', target, source]
        opts = {'wait_builds': []}
        priority = None

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.build.return_value = task_id
        # Run it and check immediate output
        # args: --quiet, target, srpm
        # expected: success
        rv = handle_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = '\n'
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag)
        unique_path_mock.assert_called_once_with('cli-build')
        self.assertEqual(running_in_bg_mock.call_count, 2)
        # callback==None
        self.session.uploadWrapper.assert_called_once_with(
            source, 'random_path', callback=None)
        self.session.build.assert_called_once_with(
            'random_path/' + source, target, opts, priority=priority)
        self.session.logout.assert_called_once()
        watch_tasks_mock.assert_called_once_with(
            self.session, [task_id], quiet=quiet,
            poll_interval=self.options.poll_interval)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.unique_path', return_value='random_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_wait(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            unique_path_mock,
            activate_session_mock,
            stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        target_info = {'dest_tag': dest_tag}
        dest_tag_info = {'locked': False}
        source = 'srpm'
        task_id = 1
        quiet = None
        args = ['--wait', target, source]
        opts = {'wait_builds': []}
        priority = None

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.build.return_value = task_id
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
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag)
        unique_path_mock.assert_called_once_with('cli-build')
        # the second one won't be executed when wait==False
        self.assertEqual(running_in_bg_mock.call_count, 1)
        self.session.uploadWrapper.assert_called_once_with(
            source, 'random_path', callback=_progress_callback)
        self.session.build.assert_called_once_with(
            'random_path/' + source, target, opts, priority=priority)
        self.session.logout.assert_called_once()
        watch_tasks_mock.assert_called_once_with(
            self.session, [task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.unique_path', return_value='random_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_nowait(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            unique_path_mock,
            activate_session_mock,
            stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        target_info = {'dest_tag': dest_tag}
        dest_tag_info = {'locked': False}
        source = 'srpm'
        task_id = 1
        args = ['--nowait', target, source]
        opts = {'wait_builds': []}
        priority = None

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.build.return_value = task_id
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
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag)
        unique_path_mock.assert_called_once_with('cli-build')
        # the second one won't be executed when wait==False
        self.assertEqual(running_in_bg_mock.call_count, 1)
        self.session.uploadWrapper.assert_called_once_with(
            source, 'random_path', callback=_progress_callback)
        self.session.build.assert_called_once_with(
            'random_path/' + source, target, opts, priority=priority)
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()
        self.assertIsNone(rv)
