from __future__ import absolute_import
from __future__ import print_function
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_resubmit
from . import utils


class TestResubmit(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.task_id = 101
        self.taskinfo = """Task: 101
Type: createrepo
Owner: kojiadmin
State: closed
Created: Thu Oct 12 20:29:29 2017
Started: Thu Oct 12 20:29:44 2017
Finished: Thu Oct 12 20:33:11 2017
Host: kojibuilder
Log Files:
  /mnt/koji/work/tasks/2/2/createrepo.log
  /mnt/koji/work/tasks/2/2/mergerepos.log
"""

        self.error_format = """Usage: %s resubmit [options] <task_id>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.watch_tasks')
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_resubmit(
            self,
            activate_session_mock,
            watch_tasks_mock,
            stderr,
            stdout):
        """Test handle_resubmit function"""
        arguments = [str(self.task_id)]
        options = mock.MagicMock(quiet=False)
        new_task_id = self.task_id + 100

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.logout.return_value = None
        session.resubmitTask.return_value = new_task_id
        session.getTaskInfo.return_value = None

        # Generate task info and nowait tests
        with mock.patch('koji_cli.commands._printTaskInfo') as p_mock:
            p_mock.side_effect = lambda *args, **kwargs: print(self.taskinfo)
            handle_resubmit(options, session, arguments + ['--nowait'])
        activate_session_mock.assert_called_with(session, options)
        expected = "Resubmitting the following task:" + "\n"
        expected += self.taskinfo + "\n"
        expected += "Resubmitted task %s as new task %s" % \
                    (self.task_id, new_task_id) + "\n"
        self.assert_console_message(stdout, expected)

        session.logout.reset_mock()
        session.resubmitTask.reset_mock()
        session.resubmitTask.return_value = new_task_id

        # Quiet and watch tasks tests
        arguments.append('--quiet')
        with mock.patch('koji_cli.commands._running_in_bg') as run_bg_mock:
            run_bg_mock.return_value = False
            self.assertTrue(handle_resubmit(options, session, arguments))
            run_bg_mock.assert_called_once()
        watch_tasks_mock.assert_called_with(
            session,
            [new_task_id],
            quiet=True,
            poll_interval=options.poll_interval)
        session.logout.assert_called_once()
        session.resubmitTask.assert_called_with(self.task_id)
        session.resubmitTask.assert_called_once()
        self.assert_console_message(stdout, '')

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_resubmit_argument_error(
            self, activate_session_mock, stderr, stdout):
        """Test handle_resubmit argument error"""
        arguments = []
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        expected = self.format_error_message(
            "Please specify a single task ID")

        self.assert_system_exit(
            handle_resubmit,
            options,
            session,
            arguments,
            stderr=expected,
            activate_session=None)

        # Check there is no message on stdout
        self.assert_console_message(stdout, '')

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()

    def test_handle_resubmit_help(self):
        """Test handle_resubmit help message output"""
        self.assert_help(
            handle_resubmit,
            """Usage: %s resubmit [options] <task_id>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
  --nowait    Don't wait on task
  --nowatch   An alias for --nowait
  --quiet     Do not print the task information
""" % self.progname)

if __name__ == '__main__':
    unittest.main()
