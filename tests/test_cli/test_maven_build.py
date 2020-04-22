from __future__ import absolute_import

import mock
import optparse
import os
import six
import sys
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_maven_build
from . import utils

EMPTY_BUILD_OPTS = {
    'specfile': None,
    'nowait': None,
    'patches': None,
    'envs': [],
    'scratch': None,
    'section': None,
    'quiet': None,
    'profiles': [],
    'skip_tag': None,
    'jvm_options': [],
    'goals': [],
    'background': None,
    'maven_options': [],
    'debug': None,
    'packages': [],
    'properties': [],
    'inis': []}


class TestMavenBuild(utils.CliTestCase):
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

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_maven_build(self, watch_tasks_mock, running_in_bg_mock,
                                activate_session_mock, stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        target_info = {'dest_tag': dest_tag_id, 'dest_tag_name': dest_tag}
        dest_tag_info = {'id': dest_tag_id, 'name': dest_tag, 'locked': False}
        source = 'http://scm'
        task_id = 1
        args = [target, source]
        opts = {}
        priority = None

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.mavenBuild.return_value = task_id
        # Run it and check immediate output
        # args: target http://scm
        # expected: success
        rv = handle_maven_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag_id)
        self.session.mavenBuild.assert_called_once_with(
            source, target, opts, priority=priority)
        running_in_bg_mock.assert_called_once()
        self.session.logout.assert_called()
        watch_tasks_mock.assert_called_once_with(
            self.session, [task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_maven_build_no_arg(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            activate_session_mock,
            stderr,
            stdout):
        args = []
        progname = os.path.basename(sys.argv[0]) or 'koji'

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            handle_maven_build(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = ''
        expected_stderr = """Usage: %s maven-build [options] <target> <URL>
       %s maven-build --ini=CONFIG... [options] <target>
(Specify the --help global option for a list of other help options)

%s: error: Exactly two arguments (a build target and a SCM URL) are required
""" % (progname, progname, progname)
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        running_in_bg_mock.assert_not_called()
        self.session.mavenBuild.assert_not_called()
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_maven_build_no_arg_with_ini(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            activate_session_mock,
            stderr,
            stdout):
        args = ['--ini=config.ini']
        progname = os.path.basename(sys.argv[0]) or 'koji'

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            handle_maven_build(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = ''
        expected_stderr = """Usage: %s maven-build [options] <target> <URL>
       %s maven-build --ini=CONFIG... [options] <target>
(Specify the --help global option for a list of other help options)

%s: error: Exactly one argument (a build target) is required
""" % (progname, progname, progname)
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        running_in_bg_mock.assert_not_called()
        self.session.mavenBuild.assert_not_called()
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_maven_build_help(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            activate_session_mock,
            stderr,
            stdout):
        args = ['--help']
        progname = os.path.basename(sys.argv[0]) or 'koji'

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            handle_maven_build(self.options, self.session, args)
        self.assertExitCode(ex, 0)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = """Usage: %s maven-build [options] <target> <URL>
       %s maven-build --ini=CONFIG... [options] <target>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --patches=URL         SCM URL of a directory containing patches to apply to
                        the sources before building
  -G GOAL, --goal=GOAL  Additional goal to run before "deploy"
  -P PROFILE, --profile=PROFILE
                        Enable a profile for the Maven build
  -D NAME=VALUE, --property=NAME=VALUE
                        Pass a system property to the Maven build
  -E NAME=VALUE, --env=NAME=VALUE
                        Set an environment variable
  -p PACKAGE, --package=PACKAGE
                        Install an additional package into the buildroot
  -J OPTION, --jvm-option=OPTION
                        Pass a command-line option to the JVM
  -M OPTION, --maven-option=OPTION
                        Pass a command-line option to Maven
  --ini=CONFIG          Pass build parameters via a .ini file
  -s SECTION, --section=SECTION
                        Get build parameters from this section of the .ini
  --debug               Run Maven build in debug mode
  --specfile=URL        SCM URL of a spec file fragment to use to generate
                        wrapper RPMs
  --skip-tag            Do not attempt to tag package
  --scratch             Perform a scratch build
  --nowait              Don't wait on build
  --quiet               Do not print the task information
  --background          Run the build at a lower priority
""" % (progname, progname)
        expected_stderr = ''
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()

        running_in_bg_mock.assert_not_called()
        self.session.mavenBuild.assert_not_called()
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_maven_build_target_not_found(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            activate_session_mock,
            stderr):
        target = 'target'
        target_info = None
        source = 'http://scm'
        args = [target, source]

        progname = os.path.basename(sys.argv[0]) or 'koji'

        self.session.getBuildTarget.return_value = target_info
        # Run it and check immediate output
        # args: target http://scm
        # expected: failed, target not found
        with self.assertRaises(SystemExit) as ex:
            handle_maven_build(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        actual = stderr.getvalue()
        expected = """Usage: %s maven-build [options] <target> <URL>
       %s maven-build --ini=CONFIG... [options] <target>
(Specify the --help global option for a list of other help options)

%s: error: Unknown build target: target
""" % (progname, progname, progname)
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_not_called()
        running_in_bg_mock.assert_not_called()
        self.session.mavenBuild.assert_not_called()
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_dest_tag_not_found(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            activate_session_mock,
            stderr):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        target_info = {'dest_tag': dest_tag_id, 'dest_tag_name': dest_tag}
        dest_tag_info = None
        source = 'http://scm'
        args = [target, source]

        progname = os.path.basename(sys.argv[0]) or 'koji'

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        # Run it and check immediate output
        # args: target http://scm
        # expected: failed, dest_tag not found
        with self.assertRaises(SystemExit) as ex:
            handle_maven_build(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        actual = stderr.getvalue()
        expected = """Usage: %s maven-build [options] <target> <URL>
       %s maven-build --ini=CONFIG... [options] <target>
(Specify the --help global option for a list of other help options)

%s: error: Unknown destination tag: dest_tag
""" % (progname, progname, progname)
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag_id)
        running_in_bg_mock.assert_not_called()
        self.session.mavenBuild.assert_not_called()
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_dest_tag_locked(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            activate_session_mock,
            stderr):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        target_info = {'dest_tag': dest_tag_id, 'dest_tag_name': dest_tag}
        dest_tag_info = {'id': 2, 'name': dest_tag, 'locked': True}
        source = 'http://scm'
        args = [target, source]

        progname = os.path.basename(sys.argv[0]) or 'koji'

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        # Run it and check immediate output
        # args: target http://scm
        # expected: failed, dest_tag is locked
        with self.assertRaises(SystemExit) as ex:
            handle_maven_build(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        actual = stderr.getvalue()
        expected = """Usage: %s maven-build [options] <target> <URL>
       %s maven-build --ini=CONFIG... [options] <target>
(Specify the --help global option for a list of other help options)

%s: error: Destination tag dest_tag is locked
""" % (progname, progname, progname)
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag_id)
        running_in_bg_mock.assert_not_called()
        self.session.mavenBuild.assert_not_called()
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch(
        'koji.util.parse_maven_param',
        return_value={
            'section': {
                'scmurl': 'http://iniscmurl',
                'packages': [
                    'pkg1',
                    'pkg2']}})
    @mock.patch('koji.util.maven_opts')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_inis(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            maven_opts_mock,
            parse_maven_param_mock,
            activate_session_mock,
            stdout,
            stderr):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        target_info = {'dest_tag': dest_tag_id, 'dest_tag_name': dest_tag}
        dest_tag_info = {'id': 2, 'name': dest_tag, 'locked': False}
        source = 'http://iniscmurl'
        section = 'section'
        args = [
            '--ini=config1.ini',
            '--ini=config2.ini',
            '--section=' +
            section,
            target]
        scratch = None
        build_opts = EMPTY_BUILD_OPTS.copy()
        build_opts['section'] = section
        build_opts['inis'] = ['config1.ini', 'config2.ini']
        build_opts = optparse.Values(build_opts)
        opts = {'packages': ['pkg1', 'pkg2']}
        task_id = 1
        priority = None
        progname = os.path.basename(sys.argv[0]) or 'koji'

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.mavenBuild.return_value = task_id
        # Run it and check immediate output
        # args: --ini=config1.ini --ini=config2.ini --section=section target
        # expected: success
        rv = handle_maven_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag_id)
        parse_maven_param_mock.assert_called_once_with(
            build_opts.inis, scratch=scratch, section=section)
        maven_opts_mock.assert_not_called()
        self.session.mavenBuild.assert_called_once_with(
            source, target, opts, priority=priority)
        running_in_bg_mock.assert_called_once()
        self.session.logout.assert_called_once()
        watch_tasks_mock.assert_called_once_with(
            self.session, [task_id], quiet=build_opts.quiet,
            poll_interval=self.options.poll_interval)
        self.assertEqual(rv, 0)

        stdout.seek(0)
        stdout.truncate()
        self.options.reset_mock()
        parse_maven_param_mock.reset_mock()
        parse_maven_param_mock.return_value = {
            'section': {
                'type': 'other',
                'scmurl': 'http://iniscmurl',
                'packages': [
                    'pkg1',
                    'pkg2']}}
        self.session.reset_mock()
        # Run it and check immediate output
        # args: --ini=config1.ini --ini=config2.ini --section=section target
        # expected: failed, no type == 'maven' found
        with self.assertRaises(SystemExit) as ex:
            handle_maven_build(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        actual = stderr.getvalue()
        expected = """Usage: %s maven-build [options] <target> <URL>
       %s maven-build --ini=CONFIG... [options] <target>
(Specify the --help global option for a list of other help options)

%s: error: Section section does not contain a maven-build config
""" % (progname, progname, progname)
        self.assertMultiLineEqual(actual, expected)
        self.assertMultiLineEqual(stdout.getvalue(), '')
        parse_maven_param_mock.assert_called_once_with(
            build_opts.inis, scratch=scratch, section=section)
        maven_opts_mock.assert_not_called()
        self.session.mavenBuild.assert_not_called()

        stdout.seek(0)
        stdout.truncate()
        stderr.seek(0)
        stderr.truncate()
        self.options.reset_mock()
        parse_maven_param_mock.reset_mock()
        parse_maven_param_mock.side_effect = ValueError('errormsg')
        self.session.reset_mock()
        # Run it and check immediate output
        # args: --ini=config1.ini --ini=config2.ini --section=section target
        # expected: failed, ValueError raised when parsing .ini files
        with self.assertRaises(SystemExit) as ex:
            handle_maven_build(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        actual = stderr.getvalue()
        expected = """Usage: %s maven-build [options] <target> <URL>
       %s maven-build --ini=CONFIG... [options] <target>
(Specify the --help global option for a list of other help options)

%s: error: errormsg
""" % (progname, progname, progname)
        self.assertMultiLineEqual(actual, expected)
        self.assertMultiLineEqual(stdout.getvalue(), '')
        parse_maven_param_mock.assert_called_once_with(
            build_opts.inis, scratch=scratch, section=section)
        maven_opts_mock.assert_not_called()
        self.session.mavenBuild.assert_not_called()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji.util.parse_maven_param')
    @mock.patch('koji.util.maven_opts')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_invalid_scm(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            maven_opts_mock,
            parse_maven_param_mock,
            activate_session_mock,
            stderr):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        target_info = {'dest_tag': dest_tag_id, 'dest_tag_name': dest_tag}
        dest_tag_info = {'id': 2, 'name': dest_tag, 'locked': False}
        source = 'badscm'
        args = [target, source]
        scratch = None
        build_opts = EMPTY_BUILD_OPTS.copy()
        progname = os.path.basename(sys.argv[0]) or 'koji'

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        # Run it and check immediate output
        # args: target badscm
        # expected: failed, scm is invalid
        with self.assertRaises(SystemExit) as ex:
            handle_maven_build(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        actual = stderr.getvalue()
        expected = """Usage: %s maven-build [options] <target> <URL>
       %s maven-build --ini=CONFIG... [options] <target>
(Specify the --help global option for a list of other help options)

%s: error: Invalid SCM URL: badscm
""" % (progname, progname, progname)
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag_id)
        parse_maven_param_mock.assert_not_called()
        maven_opts_mock.assert_called_once_with(build_opts, scratch=scratch)
        running_in_bg_mock.assert_not_called()
        self.session.mavenBuild.assert_not_called()
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji.util.parse_maven_param')
    @mock.patch('koji.util.maven_opts', return_value={})
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_build_other_params(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            maven_opts_mock,
            parse_maven_param_mock,
            activate_session_mock,
            stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        target_info = {'dest_tag': dest_tag_id, 'dest_tag_name': dest_tag}
        dest_tag_info = {'id': 2, 'name': dest_tag, 'locked': False}
        source = 'http://scm'
        args = ['--debug', '--skip-tag', '--background', target, source]
        scratch = None
        priority = 5
        build_opts = EMPTY_BUILD_OPTS.copy()
        build_opts['debug'] = True
        build_opts['skip_tag'] = True
        build_opts['background'] = True
        opts = {'maven_options': ['--debug'], 'skip_tag': True}

        task_id = 1

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.mavenBuild.return_value = task_id
        # Run it and check immediate output
        # args: --debug --skip-tag --background target http://scm
        # expected: success
        rv = handle_maven_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag_id)
        parse_maven_param_mock.assert_not_called()
        maven_opts_mock.assert_called_once_with(build_opts, scratch=scratch)
        running_in_bg_mock.assert_called_once()
        self.session.mavenBuild.assert_called_once_with(
            source, target, opts, priority=priority)
        self.session.logout.assert_called_once()
        watch_tasks_mock.assert_called_once_with(
            self.session, [task_id], quiet=build_opts['quiet'],
            poll_interval=self.options.poll_interval)
        self.assertEqual(rv, 0)

        stdout.seek(0)
        stdout.truncate()
        self.options.reset_mock()
        maven_opts_mock.reset_mock()
        maven_opts_mock.return_value = {'maven_options': ['test', 'test2=val']}
        self.session.reset_mock()
        args = [
            '--debug',
            '--skip-tag',
            '--background',
            '-Mtest',
            '-Mtest2=val',
            target,
            source]
        build_opts['maven_options'] = ['test', 'test2=val']
        opts['maven_options'] = ['test', 'test2=val', '--debug']
        # Run it and check immediate output
        # args: --debug --skip-tag --background -Mtest -Mtest2=val target http://scm
        # expected: success
        handle_maven_build(self.options, self.session, args)
        self.assertMultiLineEqual(actual, expected)
        maven_opts_mock.assert_called_once_with(build_opts, scratch=scratch)
        self.session.mavenBuild.assert_called_once_with(
            source, target, opts, priority=priority)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_maven_build_quiet(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            activate_session_mock,
            stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        target_info = {'dest_tag': dest_tag_id, 'dest_tag_name': dest_tag}
        dest_tag_info = {'id': dest_tag_id, 'name': dest_tag, 'locked': False}
        source = 'http://scm'
        task_id = 1
        args = ['--quiet', target, source]
        opts = {}
        priority = None
        self.options.quiet = True

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.mavenBuild.return_value = task_id
        # Run it and check immediate output
        # args: --quiet target http://scm
        # expected: success
        rv = handle_maven_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag_id)
        self.session.mavenBuild.assert_called_once_with(
            source, target, opts, priority=priority)
        running_in_bg_mock.assert_called_once()
        self.session.logout.assert_called()
        watch_tasks_mock.assert_called_once_with(
            self.session, [task_id], quiet=self.options.quiet,
            poll_interval=self.options.poll_interval)
        self.assertEqual(rv, 0)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=True)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_maven_build_quiet(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            activate_session_mock,
            stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        target_info = {'dest_tag': dest_tag_id, 'dest_tag_name': dest_tag}
        dest_tag_info = {'id': dest_tag_id, 'name': dest_tag, 'locked': False}
        source = 'http://scm'
        task_id = 1
        args = [target, source]
        opts = {}
        priority = None

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.mavenBuild.return_value = task_id
        # Run it and check immediate output
        # args: target http://scm
        # expected: success
        rv = handle_maven_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag_id)
        self.session.mavenBuild.assert_called_once_with(
            source, target, opts, priority=priority)
        running_in_bg_mock.assert_called_once()
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()
        self.assertIsNone(rv)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji.util.parse_maven_param')
    @mock.patch('koji.util.maven_opts', return_value={})
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks', return_value=0)
    def test_handle_maven_build_nowait(
            self,
            watch_tasks_mock,
            running_in_bg_mock,
            maven_opts_mock,
            parse_maven_param_mock,
            activate_session_mock,
            stdout):
        target = 'target'
        dest_tag = 'dest_tag'
        dest_tag_id = 2
        target_info = {'dest_tag': dest_tag_id, 'dest_tag_name': dest_tag}
        dest_tag_info = {'id': dest_tag_id, 'name': dest_tag, 'locked': False}
        source = 'http://scm'
        task_id = 1
        args = ['--nowait', target, source]
        build_opts = EMPTY_BUILD_OPTS.copy()
        build_opts['nowait'] = True
        opts = {}
        priority = None
        scratch = None

        self.session.getBuildTarget.return_value = target_info
        self.session.getTag.return_value = dest_tag_info
        self.session.mavenBuild.return_value = task_id
        # Run it and check immediate output
        # args: target http://scm
        # expected: success
        rv = handle_maven_build(self.options, self.session, args)
        actual = stdout.getvalue()
        expected = """Created task: 1
Task info: weburl/taskinfo?taskID=1
"""
        self.assertMultiLineEqual(actual, expected)
        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getBuildTarget.assert_called_once_with(target)
        self.session.getTag.assert_called_once_with(dest_tag_id)
        parse_maven_param_mock.assert_not_called()
        maven_opts_mock.assert_called_once_with(build_opts, scratch=scratch)
        self.session.mavenBuild.assert_called_once_with(
            source, target, opts, priority=priority)
        running_in_bg_mock.assert_called_once()
        self.session.logout.assert_not_called()
        watch_tasks_mock.assert_not_called()
        self.assertIsNone(rv)


if __name__ == '__main__':
    unittest.main()
