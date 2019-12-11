from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_wrapper_rpm
from . import utils


class TestWrapperRpm(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.target = 'target'
        self.build = '1'
        self.scm_url = 'git+https://github.com/project/test#12345'
        self.task_id = 1

        self.error_format = """Usage: %s wrapper-rpm [options] <target> <build-id|n-v-r> <URL>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands._running_in_bg')
    @mock.patch('koji_cli.commands.watch_tasks')
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_wrapper_rpm(
            self,
            activate_session_mock,
            watch_tasks_mock,
            running_in_bg_mock,
            stderr,
            stdout):
        """Test  handle_wrapper_rpm function without --ini option"""
        arguments = [self.target, self.build, self.scm_url]
        options = mock.MagicMock(weburl='weburl')

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.logout.return_value = None
        session.wrapperRPM.return_value = self.task_id

        expected = "Created task: %d\n" % self.task_id
        expected += "Task info: %s/taskinfo?taskID=%s\n" % \
                    (options.weburl, self.task_id)

        # Background on test
        running_in_bg_mock.return_value = True

        arguments.extend(['--create-build', '--skip-tag', '--scratch'])
        self.assertEqual(None, handle_wrapper_rpm(options, session, arguments))
        self.assert_console_message(stdout, expected)

        # Background off but --nowait is specified
        running_in_bg_mock.return_value = False

        args = arguments + ['--nowait']
        self.assertEqual(None, handle_wrapper_rpm(options, session, args))
        self.assert_console_message(stdout, expected)

        # proirity test
        args = arguments + ['--nowait', '--background']
        self.assertEqual(None, handle_wrapper_rpm(options, session, args))
        self.assert_console_message(stdout, expected)

        # watch task case
        watch_tasks_mock.return_value = True
        self.assertTrue(handle_wrapper_rpm(options, session, arguments))
        self.assert_console_message(stdout, expected)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_with(session, options)
        watch_tasks_mock.assert_called_with(
            session, [self.task_id], quiet=options.quiet,
            poll_interval=options.poll_interval)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji.util.parse_maven_param')
    @mock.patch('koji_cli.commands._running_in_bg')
    @mock.patch('koji_cli.commands.watch_tasks')
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_wrapper_rpm_with_ini_config(
            self,
            activate_session_mock,
            watch_tasks_mock,
            running_in_bg_mock,
            parse_maven_mock,
            stderr,
            stdout):
        """Test  handle_wrapper_rpm function with --ini option"""
        arguments = []
        options = mock.MagicMock(weburl='weburl')

        target_info = {
            'dest_tag_name': 'dest_tag_name',
            'dest_tag': 'dest_tag'
        }

        maven_param = {
            'pkg1': {
                'type': 'wrapper',
                'scmurl': 'scmurl',
                'buildrequires': ['r1'],
                'create_build': True}
        }

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.logout.return_value = None
        session.getBuildTarget.return_value = target_info
        session.getLatestBuilds.return_value = None
        session.wrapperRPM.return_value = self.task_id
        running_in_bg_mock.return_value = False

        # With --ini option, only build target is required
        arguments = [
            self.target,
            self.build,
            self.scm_url,
            '--ini=/etc/koji.ini'
        ]
        expected = self.format_error_message(
            "Exactly one argument (a build target) is required")
        self.assert_system_exit(
            handle_wrapper_rpm,
            options,
            session,
            arguments,
            stdout='',
            stderr=expected,
            activate_session=None)

        # If koji.util.parse_maven_param has troubles
        # ValueError exception
        arguments = [self.target, '--ini=/etc/koji.ini']
        parse_maven_mock.side_effect = ValueError('fake-value-error')
        self.assert_system_exit(
            handle_wrapper_rpm,
            options,
            session,
            arguments,
            stderr={'message': '.*error: fake-value-error',
                    'regex': True}
        )

        parse_maven_mock.side_effect = None

        # type != wrapper case
        bad_param = {'pkg1': maven_param['pkg1'].copy()}
        bad_param['pkg1']['type'] = 'undefined'
        parse_maven_mock.return_value = bad_param
        self.assert_system_exit(
            handle_wrapper_rpm,
            options,
            session,
            arguments,
            stderr={'message': 'Section .* does not contain a wrapper-rpm config',
                    'regex': True}
        )

        # Lastest build does not exist case
        parse_maven_mock.return_value = maven_param
        self.assert_system_exit(
            handle_wrapper_rpm,
            options,
            session,
            arguments,
            stderr={'message': '.*error: No build of .* in %s' %
                    target_info['dest_tag_name'],
                    'regex': True}
        )

        # Check everything should work fine
        session.getLatestBuilds.return_value = [{'nvr': 'r1'}]
        handle_wrapper_rpm(options, session, arguments)
        expected = "Created task: %d\n" % self.task_id
        expected += "Task info: %s/taskinfo?taskID=%s\n" % \
                    (options.weburl, self.task_id)
        self.assert_console_message(stdout, expected)

        activate_session_mock.assert_called_with(session, options)
        watch_tasks_mock.assert_called_with(
            session, [self.task_id], quiet=options.quiet,
            poll_interval=options.poll_interval)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_wrapper_rpm_argument_error(
            self, activate_session_mock, stderr, stdout):
        """Test  handle_wrapper_rpm help message output"""
        arguments = []
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        expected = self.format_error_message(
            "You must provide a build target, a build ID or NVR, and a SCM URL to a specfile fragment")
        self.assert_system_exit(
            handle_wrapper_rpm,
            options,
            session,
            arguments,
            stdout='',
            stderr=expected,
            activate_session=None)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()

    def test_handle_wrapper_rpm_help(self):
        """Test  handle_wrapper_rpm help message output"""
        self.assert_help(
            handle_wrapper_rpm,
            """Usage: %s wrapper-rpm [options] <target> <build-id|n-v-r> <URL>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --create-build        Create a new build to contain wrapper rpms
  --ini=CONFIG          Pass build parameters via a .ini file
  -s SECTION, --section=SECTION
                        Get build parameters from this section of the .ini
  --skip-tag            If creating a new build, don't tag it
  --scratch             Perform a scratch build
  --nowait              Don't wait on build
  --background          Run the build at a lower priority
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
