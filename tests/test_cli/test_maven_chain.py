from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_maven_chain
from . import utils


class TestMavenChain(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.target = 'target'
        self.config = 'config'
        self.task_id = 101

        self.error_format = """Usage: %s maven-chain [options] <target> <config> [<config> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

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
        expected = self.format_error_message(
            "Unknown build target: %s" % self.target)
        self.assert_system_exit(
            handle_maven_chain,
            options,
            session,
            arguments,
            stderr=expected)

        # Unknow destination tag test
        session.getBuildTarget.return_value = target_info
        expected = self.format_error_message(
            "Unknown destination tag: %s" % target_info['dest_tag_name'])
        self.assert_system_exit(
            handle_maven_chain,
            options,
            session,
            arguments,
            stderr=expected)

        # Distination is locked and --scratch is not specified
        session.getTag.return_value = tag_info
        expected = self.format_error_message(
            "Destination tag %s is locked" % tag_info['name'])
        self.assert_system_exit(
            handle_maven_chain,
            options,
            session,
            arguments,
            stderr=expected)

        # Test ValueError exception asserted in parse_maven_chain
        arguments.extend(['--skip-tag', '--scratch',
                          '--force', '--background'])
        parse_maven_chain_mock.side_effect = ValueError('fake-value-error')
        expected = self.format_error_message("fake-value-error")
        self.assert_system_exit(
            handle_maven_chain,
            options,
            session,
            arguments,
            stderr=expected)

        # Background or --nowait is true
        parse_maven_chain_mock.side_effect = None
        parse_maven_chain_mock.return_value = 'build'
        handle_maven_chain(options, session, arguments + ['--nowait'])
        expected = "Created task: %d\n" % self.task_id
        expected += "Task info: %s/taskinfo?taskID=%s\n" % \
                    (options.weburl, self.task_id)
        self.assert_console_message(stdout, expected)

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
        self.assert_console_message(stdout, expected)

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
    def test_handle_maven_no_argument_error(
            self,
            activate_session_mock,
            stderr,
            stdout):
        """Test handle_maven_chain no argument error"""
        arguments = []
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        expected = self.format_error_message(
            "Two arguments (a build target and a config file) are required")
        self.assert_system_exit(
            handle_maven_chain,
            options,
            session,
            arguments,
            stdout='',
            stderr=expected,
            activate_session=None)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()

    def test_handle_maven_chain_help(self):
        """Test handle_maven_chain help message full output"""
        self.assert_help(
            handle_maven_chain,
            """Usage: %s maven-chain [options] <target> <config> [<config> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help    show this help message and exit
  --skip-tag    Do not attempt to tag builds
  --scratch     Perform scratch builds
  --debug       Run Maven build in debug mode
  --force       Force rebuilds of all packages
  --nowait      Don't wait on build
  --background  Run the build at a lower priority
""" % (self.progname))


if __name__ == '__main__':
    unittest.main()
