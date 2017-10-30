from __future__ import absolute_import
import mock
import os
import six
import sys
import unittest

from koji_cli.commands import handle_maven_chain


class TestMavenChain(unittest.TestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.progname = os.path.basename(sys.argv[0]) or 'koji'
        self.target = 'target'
        self.config = 'config'
        self.task_id = 101

    def format_error_message(self, message):
        return """Usage: %s maven-chain [options] target config...
(Specify the --help global option for a list of other help options)

%s: error: %s
""" % (self.progname, self.progname, message)

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
    @mock.patch('koji.util.parse_maven_chain')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.watch_tasks')
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_maven_chain(
            self,
            activate_session_mock,
            watch_tasks_mock,
            running_in_bg_mock,
            parse_maven_chain_mock,
            stderr,
            stdout):
        """Test handle_maven_chain function"""
        arguments = [self.target, self.config]
        options = mock.MagicMock(weburl='weburl')

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.logout.return_value = None
        session.getBuildTarget.return_value = None
        session.getTag.return_value = None
        session.chainMaven.return_value = self.task_id

        target_info = {
            'dest_tag_name': 'dest_tag_name',
            'dest_tag': 'dest_tag'
        }

        tag_info = {
            'name': 'dest_tag',
            'locked': True
        }

        # Unknonw target test
        with self.assertRaises(SystemExit) as cm:
            handle_maven_chain(options, session, arguments)
        expected = self.format_error_message("Unknown build target: %s" %
                                             self.target)
        self.assert_console_output(stderr, expected)
        self.assertEqual(cm.exception.code, 2)

        # Unknow destination tag test
        session.getBuildTarget.return_value = target_info
        with self.assertRaises(SystemExit) as cm:
            handle_maven_chain(options, session, arguments)
        expected = self.format_error_message("Unknown destination tag: %s" %
                                             target_info['dest_tag_name'])
        self.assert_console_output(stderr, expected)
        self.assertEqual(cm.exception.code, 2)

        # Distination is locked and --scratch is not specified
        session.getTag.return_value = tag_info
        with self.assertRaises(SystemExit) as cm:
            handle_maven_chain(options, session, arguments)
        expected = self.format_error_message("Destination tag %s is locked" %
                                             tag_info['name'])
        self.assert_console_output(stderr, expected)
        self.assertEqual(cm.exception.code, 2)

        # Test ValueError exception asserted in parse_maven_chain
        arguments.extend(['--skip-tag', '--scratch',
                          '--force', '--background'])
        parse_maven_chain_mock.side_effect = ValueError('fake-value-error')
        with self.assertRaises(SystemExit) as cm:
            handle_maven_chain(options, session, arguments)
        expected = self.format_error_message("fake-value-error")
        self.assert_console_output(stderr, expected)
        self.assertEqual(cm.exception.code, 2)

        # Background or --nowait is true
        parse_maven_chain_mock.side_effect = None
        parse_maven_chain_mock.return_value = 'build'
        handle_maven_chain(options, session, arguments + ['--nowait'])
        expected = "Created task: %d\n" % self.task_id
        expected += "Task info: %s/taskinfo?taskID=%s\n" % \
                    (options.weburl, self.task_id)
        self.assert_console_output(stdout, expected)

        # reset  mocks to run full test
        activate_session_mock.reset_mock()
        parse_maven_chain_mock.reset_mock()
        running_in_bg_mock.reset_mock()
        watch_tasks_mock.reset_mock()

        # Foreground/wait for task test
        watch_tasks_mock.return_value = True
        self.assertTrue(handle_maven_chain(options, session, arguments))
        expected = "Created task: %d\n" % self.task_id
        expected += "Task info: %s/taskinfo?taskID=%s\n" % \
                    (options.weburl, self.task_id)
        self.assert_console_output(stdout, expected)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_with(session, options)
        parse_maven_chain_mock.assert_called_with([self.config], scratch=True)
        session.chainMaven.assert_called_with('build', self.target,
                                              {'skip_tag': True,
                                               'scratch': True,
                                               'force': True},
                                              priority=5)
        running_in_bg_mock.assert_called()
        watch_tasks_mock.assert_called_with(
            session, [self.task_id], quiet=options.quiet,
            poll_interval=options.poll_interval)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_maven_chain_help_compat(
            self,
            activate_session_mock,
            stderr,
            stdout):
        """Test handle_maven_chain help message compact output"""
        arguments = []
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as cm:
            handle_maven_chain(options, session, arguments)
        expected_stderr = self.format_error_message(
            "Two arguments (a build target and a config file) are required")
        self.assert_console_output(stdout, '')
        self.assert_console_output(stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        self.assertEqual(cm.exception.code, 2)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_maven_chain_help_full(
            self, activate_session_mock, stderr, stdout):
        """Test handle_maven_chain help message full output"""
        arguments = ['--help']
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as cm:
            handle_maven_chain(options, session, arguments)
        expected_stdout = """Usage: %s maven-chain [options] target config...
(Specify the --help global option for a list of other help options)

Options:
  -h, --help    show this help message and exit
  --skip-tag    Do not attempt to tag builds
  --scratch     Perform scratch builds
  --debug       Run Maven build in debug mode
  --force       Force rebuilds of all packages
  --nowait      Don't wait on build
  --background  Run the build at a lower priority
""" % (self.progname)
        self.assert_console_output(stdout, expected_stdout)
        self.assert_console_output(stderr, '')

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        self.assertEqual(cm.exception.code, 0)

if __name__ == '__main__':
    unittest.main()
