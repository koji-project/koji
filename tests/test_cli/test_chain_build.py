from __future__ import absolute_import

import mock
import six
import unittest

from koji_cli.commands import handle_chain_build
from . import utils


class TestChainBuild(utils.CliTestCase):

    def setUp(self):
        # Show long diffs in error output...
        self.maxDiff = None
        # Mock out the options parsed in main
        self.options = mock.MagicMock()
        self.options.quiet = None
        self.options.weburl = 'weburl'
        self.options.poll_interval = 0
        # Mock out the xmlrpc server
        self.session = mock.MagicMock()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.running_in_bg_mock = mock.patch('koji_cli.commands._running_in_bg').start()
        self.running_in_bg_mock.return_value = False
        self.watch_tasks_mock = mock.patch('koji_cli.commands.watch_tasks').start()
        self.watch_tasks_mock.return_value = 0
        self.error_format = """Usage: %s chain-build [options] <target> <URL> [<URL> [:] <URL> [:] <URL> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_chain_build(self, stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        build_tag = 'build_tag'
        build_tag_id = 3
        target_info = {
            'dest_tag': dest_tag_id,
            'dest_tag_name': dest_tag,
            'build_tag': build_tag_id,
            'build_tag_name': build_tag}
        dest_tag_info = {'id': 2, 'name': dest_tag, 'locked': False}
        tag_tree = [{'parent_id': 2}, {'parent_id': 4}, {'parent_id': 5}]
        source_args = [
            'http://scm1',
            ':',
            'http://scm2',
            'http://scm3',
            'n-v-r-1',
            ':',
            'n-v-r-2',
            'n-v-r-3']
        sources = [['http://scm1'], ['http://scm2',
                                     'http://scm3', 'n-v-r-1'], ['n-v-r-2', 'n-v-r-3']]
        task_id = 1
        args = [target] + source_args
        priority = None

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.getFullInheritance.return_value = tag_tree
        self.session.chainBuild.return_value = task_id
        # Run it and check immediate output
        # args: target http://scm1 : http://scm2 http://scm3 n-v-r-1 : n-v-r-2 n-v-r-3
        # expected: success
        rv = handle_chain_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag_id, strict=True)
        self.session.getFullInheritance.assert_called_once_with(build_tag_id)
        self.session.chainBuild.assert_called_once_with(sources, target, priority=priority)
        self.running_in_bg_mock.assert_called_once()
        self.session.logout.assert_called()
        self.watch_tasks_mock.assert_called_once_with(
            self.session, [task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval, topurl=self.options.topurl)
        self.assertEqual(rv, 0)

    def test_handle_chain_build_no_arg(self):
        arguments = []

        # Run it and check immediate output
        self.assert_system_exit(
            handle_chain_build,
            self.options, self.session, arguments,
            stderr=self.format_error_message(
                "At least two arguments (a build target and a SCM URL) are required"),
            stdout='',
            activate_session=None,
            exit_code=2)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.getFullInheritance.assert_not_called()
        self.running_in_bg_mock.assert_not_called()
        self.session.chainBuild.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    def test_handle_chain_build_help(self):
        self.assert_help(
            handle_chain_build,
            """Usage: %s chain-build [options] <target> <URL> [<URL> [:] <URL> [:] <URL> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help    show this help message and exit
  --wait        Wait on build, even if running in the background
  --nowait      Don't wait on build
  --quiet       Do not print the task information
  --background  Run the build at a lower priority
""" % self.progname)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.getFullInheritance.assert_not_called()
        self.running_in_bg_mock.assert_not_called()
        self.session.chainBuild.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    def test_handle_chain_build_target_not_found(self):
        target = 'target'
        target_info = None
        source_args = [
            'http://scm1',
            ':',
            'http://scm2',
            'http://scm3',
            'n-v-r-1',
            ':',
            'n-v-r-2',
            'n-v-r-3']
        arguments = [target] + source_args

        self.session.getBuildTarget.return_value = target_info
        # Run it and check immediate output
        # args: target http://scm1 : http://scm2 http://scm3 n-v-r-1 : n-v-r-2 n-v-r-3
        # expected: failed, target not found
        self.assert_system_exit(
            handle_chain_build,
            self.options, self.session, arguments,
            stderr=self.format_error_message("No such build target: target"),
            stdout='',
            activate_session=None,
            exit_code=2)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_not_called()
        self.session.getFullInheritance.assert_not_called()
        self.running_in_bg_mock.assert_not_called()
        self.session.chainBuild.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    def test_handle_build_dest_tag_locked(self):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        build_tag = 'build_tag'
        build_tag_id = 3
        target_info = {
            'dest_tag': dest_tag_id,
            'dest_tag_name': dest_tag,
            'build_tag': build_tag_id,
            'build_tag_name': build_tag}
        dest_tag_info = {'id': 2, 'name': dest_tag, 'locked': True}
        source_args = [
            'http://scm1',
            ':',
            'http://scm2',
            'http://scm3',
            'n-v-r-1',
            ':',
            'n-v-r-2',
            'n-v-r-3']
        arguments = [target] + source_args

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        # Run it and check immediate output
        # args: target http://scm1 : http://scm2 http://scm3 n-v-r-1 : n-v-r-2 n-v-r-3
        # expected: failed, dest_tag is locked
        self.assert_system_exit(
            handle_chain_build,
            self.options, self.session, arguments,
            stderr=self.format_error_message("Destination tag dest_tag is locked"),
            stdout='',
            activate_session=None,
            exit_code=2)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag_id, strict=True)
        self.session.getFullInheritance.assert_not_called()
        self.running_in_bg_mock.assert_not_called()
        self.session.chainBuild.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    def test_handle_build_dest_tag_not_inherited_by_build_tag(self):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        build_tag = 'build_tag'
        build_tag_id = 3
        target_info = {
            'name': target,
            'dest_tag': dest_tag_id,
            'dest_tag_name': dest_tag,
            'build_tag': build_tag_id,
            'build_tag_name': build_tag}
        dest_tag_info = {'id': 2, 'name': dest_tag, 'locked': False}
        tag_tree = [{'parent_id': 4}, {'parent_id': 5}]
        source_args = [
            'http://scm1',
            ':',
            'http://scm2',
            'http://scm3',
            'n-v-r-1',
            ':',
            'n-v-r-2',
            'n-v-r-3']
        arguments = [target] + source_args

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.getFullInheritance.return_value = tag_tree
        # Run it and check immediate output
        # args: target, target http://scm1 : http://scm2 http://scm3 n-v-r-1 : n-v-r-2 n-v-r-3
        # expected: failed, dest_tag is not in build_tag's inheritance
        expected = """Packages in destination tag dest_tag are not inherited by build tag build_tag
Target target is not usable for a chain-build
"""
        self.assert_system_exit(
            handle_chain_build,
            self.options, self.session, arguments,
            stderr=expected,
            stdout='',
            activate_session=None,
            exit_code=1)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag_id, strict=True)
        self.session.getFullInheritance.assert_called_once_with(build_tag_id)
        self.running_in_bg_mock.assert_not_called()
        self.session.chainBuild.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    def test_handle_chain_build_invalidated_src(self):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        build_tag = 'build_tag'
        build_tag_id = 3
        target_info = {
            'dest_tag': dest_tag_id,
            'dest_tag_name': dest_tag,
            'build_tag': build_tag_id,
            'build_tag_name': build_tag}
        dest_tag_info = {'id': 2, 'name': dest_tag, 'locked': False}
        tag_tree = [{'parent_id': 2}, {'parent_id': 4}, {'parent_id': 5}]
        source_args = [
            'badnvr',
            ':',
            'http://scm2',
            'http://scm3',
            'n-v-r-1',
            ':',
            'n-v-r-2',
            'n-v-r-3']
        args = [target] + source_args

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.getFullInheritance.return_value = tag_tree
        with mock.patch('sys.stderr', new_callable=six.StringIO) as stderr:
            # Run it and check immediate output
            # args: target badnvr : http://scm2 http://scm3 n-v-r-1 : n-v-r-2 n-v-r-3
            # expected: failed, src is neither scm nor good n-v-r
            with self.assertRaises(SystemExit) as ex:
                handle_chain_build(self.options, self.session, args)
            self.assertExitCode(ex, 1)
            actual = stderr.getvalue()
            expected = '"badnvr" is not a SCM URL or package N-V-R\n'
            self.assertMultiLineEqual(actual, expected)
            # Finally, assert that things were called as we expected.
            self.activate_session_mock.assert_called_once_with(self.session, self.options)
            self.session.getBuildTarget.assert_called_once_with(target)
            self.session.getTag.assert_called_once_with(
                dest_tag_id, strict=True)
            self.session.getFullInheritance.assert_called_once_with(
                build_tag_id)
            self.session.chainBuild.assert_not_called()
            self.running_in_bg_mock.assert_not_called()
            self.session.logout.assert_not_called()
            self.watch_tasks_mock.assert_not_called()

        with mock.patch('sys.stderr', new_callable=six.StringIO) as stderr:
            source_args = [
                'path/n-v-r',
                ':',
                'http://scm2',
                'http://scm3',
                'n-v-r-1',
                ':',
                'n-v-r-2',
                'n-v-r-3']
            args = [target] + source_args
            # args: target path/n-v-r : http://scm2 http://scm3 n-v-r-1 : n-v-r-2 n-v-r-3
            # expected: failed
            with self.assertRaises(SystemExit) as ex:
                handle_chain_build(self.options, self.session, args)
            self.assertExitCode(ex, 1)
            actual = stderr.getvalue()
            expected = '"path/n-v-r" is not a SCM URL or package N-V-R\n'
            self.assertMultiLineEqual(actual, expected)

        with mock.patch('sys.stderr', new_callable=six.StringIO) as stderr:
            source_args = [
                'badn-vr',
                ':',
                'http://scm2',
                'http://scm3',
                'n-v-r-1',
                ':',
                'n-v-r-2',
                'n-v-r-3']
            args = [target] + source_args
            # args: target badn-vr : http://scm2 http://scm3 n-v-r-1 : n-v-r-2 n-v-r-3
            # expected: failed
            with self.assertRaises(SystemExit) as ex:
                handle_chain_build(self.options, self.session, args)
            self.assertExitCode(ex, 1)
            actual = stderr.getvalue()
            expected = '"badn-vr" is not a SCM URL or package N-V-R\n'
            self.assertMultiLineEqual(actual, expected)

        with mock.patch('sys.stderr', new_callable=six.StringIO) as stderr:
            source_args = [
                'badn-v-r.rpm',
                ':',
                'http://scm2',
                'http://scm3',
                'n-v-r-1',
                ':',
                'n-v-r-2',
                'n-v-r-3']
            args = [target] + source_args
            # args: target badn-v-r.rpm : http://scm2 http://scm3 n-v-r-1 : n-v-r-2 n-v-r-3
            # expected: failed
            with self.assertRaises(SystemExit) as ex:
                handle_chain_build(self.options, self.session, args)
            self.assertExitCode(ex, 1)
            actual = stderr.getvalue()
            expected = '"badn-v-r.rpm" is not a SCM URL or package N-V-R\n'
            self.assertMultiLineEqual(actual, expected)

        with mock.patch('sys.stderr', new_callable=six.StringIO) as stderr:
            source_args = ['http://scm']
            args = [target] + source_args

            # args: target http://scm
            # expected: failed, only one src found
            with self.assertRaises(SystemExit) as ex:
                handle_chain_build(self.options, self.session, args)
            self.assertExitCode(ex, 2)
            actual = stderr.getvalue()
            expected = self.format_error_message(
                "You must specify at least one dependency between builds with : (colon)\n"
                "If there are no dependencies, use the build command instead")
            self.assertMultiLineEqual(actual, expected)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_chain_build_background(self, stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        build_tag = 'build_tag'
        build_tag_id = 3
        target_info = {
            'dest_tag': dest_tag_id,
            'dest_tag_name': dest_tag,
            'build_tag': build_tag_id,
            'build_tag_name': build_tag}
        dest_tag_info = {'id': 2, 'name': dest_tag, 'locked': False}
        tag_tree = [{'parent_id': 2}, {'parent_id': 4}, {'parent_id': 5}]
        source_args = [
            'http://scm1',
            ':',
            'http://scm2',
            'http://scm3',
            'n-v-r-1',
            ':',
            'n-v-r-2',
            'n-v-r-3']
        sources = [['http://scm1'], ['http://scm2',
                                     'http://scm3', 'n-v-r-1'], ['n-v-r-2', 'n-v-r-3']]
        task_id = 1
        args = ['--background', target] + source_args
        priority = 5

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.getFullInheritance.return_value = tag_tree
        self.session.chainBuild.return_value = task_id
        # Run it and check immediate output
        # args: target http://scm1 : http://scm2 http://scm3 n-v-r-1 : n-v-r-2 n-v-r-3
        # expected: success
        rv = handle_chain_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag_id, strict=True)
        self.session.getFullInheritance.assert_called_once_with(build_tag_id)
        self.session.chainBuild.assert_called_once_with(
            sources, target, priority=priority)
        self.running_in_bg_mock.assert_called_once()
        self.session.logout.assert_called()
        self.watch_tasks_mock.assert_called_once_with(
            self.session, [task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval, topurl=self.options.topurl)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_chain_build_quiet(self, stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        build_tag = 'build_tag'
        build_tag_id = 3
        target_info = {
            'dest_tag': dest_tag_id,
            'dest_tag_name': dest_tag,
            'build_tag': build_tag_id,
            'build_tag_name': build_tag}
        dest_tag_info = {'id': 2, 'name': dest_tag, 'locked': False}
        tag_tree = [{'parent_id': 2}, {'parent_id': 4}, {'parent_id': 5}]
        source_args = [
            'http://scm1',
            ':',
            'http://scm2',
            'http://scm3',
            'n-v-r-1',
            ':',
            'n-v-r-2',
            'n-v-r-3']
        sources = [['http://scm1'], ['http://scm2',
                                     'http://scm3', 'n-v-r-1'], ['n-v-r-2', 'n-v-r-3']]
        task_id = 1
        self.options.quiet = True
        args = ['--quiet', target] + source_args
        priority = None

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.getFullInheritance.return_value = tag_tree
        self.session.chainBuild.return_value = task_id
        # Run it and check immediate output
        # args: target http://scm1 : http://scm2 http://scm3 n-v-r-1 : n-v-r-2 n-v-r-3
        # expected: success
        rv = handle_chain_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag_id, strict=True)
        self.session.getFullInheritance.assert_called_once_with(build_tag_id)
        self.session.chainBuild.assert_called_once_with(
            sources, target, priority=priority)
        self.running_in_bg_mock.assert_called_once()
        self.session.logout.assert_called()
        self.watch_tasks_mock.assert_called_once_with(
            self.session, [task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval, topurl=self.options.topurl)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_chain_build_running_in_bg(self, stdout):
        self.running_in_bg_mock.return_value = True
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        build_tag = 'build_tag'
        build_tag_id = 3
        target_info = {
            'dest_tag': dest_tag_id,
            'dest_tag_name': dest_tag,
            'build_tag': build_tag_id,
            'build_tag_name': build_tag}
        dest_tag_info = {'id': 2, 'name': dest_tag, 'locked': False}
        tag_tree = [{'parent_id': 2}, {'parent_id': 4}, {'parent_id': 5}]
        source_args = [
            'http://scm1',
            ':',
            'http://scm2',
            'http://scm3',
            'n-v-r-1',
            ':',
            'n-v-r-2',
            'n-v-r-3']
        sources = [['http://scm1'], ['http://scm2',
                                     'http://scm3', 'n-v-r-1'], ['n-v-r-2', 'n-v-r-3']]
        task_id = 1
        args = [target] + source_args
        priority = None

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.getFullInheritance.return_value = tag_tree
        self.session.chainBuild.return_value = task_id
        # Run it and check immediate output
        # args: target http://scm1 : http://scm2 http://scm3 n-v-r-1 : n-v-r-2 n-v-r-3
        # expected: success
        rv = handle_chain_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag_id, strict=True)
        self.session.getFullInheritance.assert_called_once_with(build_tag_id)
        self.session.chainBuild.assert_called_once_with(
            sources, target, priority=priority)
        self.running_in_bg_mock.assert_called_once()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()
        self.assertIsNone(rv)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_chain_build_nowait(self, stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        build_tag = 'build_tag'
        build_tag_id = 3
        target_info = {
            'dest_tag': dest_tag_id,
            'dest_tag_name': dest_tag,
            'build_tag': build_tag_id,
            'build_tag_name': build_tag}
        dest_tag_info = {'id': 2, 'name': dest_tag, 'locked': False}
        tag_tree = [{'parent_id': 2}, {'parent_id': 4}, {'parent_id': 5}]
        source_args = [
            'http://scm1',
            ':',
            'http://scm2',
            'http://scm3',
            'n-v-r-1',
            ':',
            'n-v-r-2',
            'n-v-r-3']
        sources = [['http://scm1'], ['http://scm2',
                                     'http://scm3', 'n-v-r-1'], ['n-v-r-2', 'n-v-r-3']]
        task_id = 1
        args = ['--nowait', target] + source_args
        priority = None

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.getFullInheritance.return_value = tag_tree
        self.session.chainBuild.return_value = task_id
        # Run it and check immediate output
        # args: target http://scm1 : http://scm2 http://scm3 n-v-r-1 : n-v-r-2 n-v-r-3
        # expected: success
        rv = handle_chain_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag_id, strict=True)
        self.session.getFullInheritance.assert_called_once_with(build_tag_id)
        self.session.chainBuild.assert_called_once_with(
            sources, target, priority=priority)
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()
        self.assertIsNone(rv)


if __name__ == '__main__':
    unittest.main()
