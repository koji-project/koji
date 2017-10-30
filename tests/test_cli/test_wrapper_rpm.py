from __future__ import absolute_import
import mock
import os
import six
import sys
import unittest

from koji_cli.commands import handle_wrapper_rpm


class TestWrapperRpm(unittest.TestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.progname = os.path.basename(sys.argv[0]) or 'koji'
        self.target = 'target'
        self.build = '1'
        self.scm_url = 'git+https://github.com/project/test#12345'
        self.task_id = 1

    def assert_console_output(self, device, expected, wipe=True, regex=False):
        if not isinstance(device, six.StringIO):
            raise TypeError('Not a StringIO object')

        output = device.getvalue()
        if not regex:
            self.assertMultiLineEqual(output, expected)
        else:
            six.assertRegex(self, output, expected)
        if wipe:
            device.truncate(0)
            device.seek(0)

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
        self.assert_console_output(stdout, expected)

        # Background off but --nowait is specified
        running_in_bg_mock.return_value = False

        args = arguments + ['--nowait']
        self.assertEqual(None, handle_wrapper_rpm(options, session, args))
        self.assert_console_output(stdout, expected)

        # proirity test
        args = arguments + ['--nowait', '--background']
        self.assertEqual(None, handle_wrapper_rpm(options, session, args))
        self.assert_console_output(stdout, expected)

        # watch task case
        watch_tasks_mock.return_value = True
        self.assertTrue(handle_wrapper_rpm(options, session, arguments))
        self.assert_console_output(stdout, expected)

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
        with self.assertRaises(SystemExit) as cm:
            handle_wrapper_rpm(options, session, arguments)
        expected_stderr = """Usage: %s wrapper-rpm [options] target build-id|n-v-r URL
(Specify the --help global option for a list of other help options)

%s: error: Exactly one argument (a build target) is required
""" % (self.progname, self.progname)
        self.assert_console_output(stdout, '')
        self.assert_console_output(stderr, expected_stderr)

        # If koji.util.parse_maven_param has troubles
        # ValueError exception
        arguments = [self.target, '--ini=/etc/koji.ini']
        with self.assertRaises(SystemExit) as cm:
            parse_maven_mock.side_effect = ValueError('fake-value-error')
            handle_wrapper_rpm(options, session, arguments)
        self.assert_console_output(
            stderr, '.*error: fake-value-error', regex=True)
        self.assertEqual(cm.exception.code, 2)

        parse_maven_mock.side_effect = None

        # type != wrapper case
        with self.assertRaises(SystemExit) as cm:
            bad_param = {'pkg1': maven_param['pkg1'].copy()}
            bad_param['pkg1']['type'] = 'undefined'
            parse_maven_mock.return_value = bad_param
            handle_wrapper_rpm(options, session, arguments)
        self.assert_console_output(
            stderr,
            'Section .* does not contain a wrapper-rpm config',
            regex=True)

        # Lastest build does not exist case
        parse_maven_mock.return_value = maven_param
        with self.assertRaises(SystemExit) as cm:
            handle_wrapper_rpm(options, session, arguments)
        self.assert_console_output(
            stderr,
            '.*error: No build of .* in %s' % target_info['dest_tag_name'],
            regex=True)

        # Check everything should work fine
        session.getLatestBuilds.return_value = [{'nvr': 'r1'}]
        handle_wrapper_rpm(options, session, arguments)
        expected = "Created task: %d\n" % self.task_id
        expected += "Task info: %s/taskinfo?taskID=%s\n" % \
                    (options.weburl, self.task_id)
        self.assert_console_output(stdout, expected)

        activate_session_mock.assert_called_with(session, options)
        watch_tasks_mock.assert_called_with(
            session, [self.task_id], quiet=options.quiet,
            poll_interval=options.poll_interval)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_wrapper_rpm_help(self, activate_session_mock,
                                     stderr, stdout):
        """Test  handle_wrapper_rpm help message output"""
        arguments = []
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as cm:
            handle_wrapper_rpm(options, session, arguments)
        expected_stderr = """Usage: %s wrapper-rpm [options] target build-id|n-v-r URL
(Specify the --help global option for a list of other help options)

%s: error: You must provide a build target, a build ID or NVR, and a SCM URL to a specfile fragment
""" % (self.progname, self.progname)
        self.assert_console_output(stdout, '')
        self.assert_console_output(stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        self.assertEqual(cm.exception.code, 2)

if __name__ == '__main__':
    unittest.main()
