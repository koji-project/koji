from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_set_task_priority
from . import utils


class TestSetTaskPriority(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s set-task-priority [options] --priority=<priority> <task_id> [<task_id> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_set_task_priority(
            self,
            activate_session_mock,
            stdout):
        """Test handle_set_task_priority function"""
        session = mock.MagicMock()
        options = mock.MagicMock()
        arguments = ['--priority', '10', '1', '11', '121', '1331']

        # Case 1. no task id error
        expected = self.format_error_message(
            "You must specify at least one task id")

        self.assert_system_exit(
            handle_set_task_priority,
            options,
            session,
            [],
            stderr=expected,
            activate_session=None)
        activate_session_mock.assert_not_called()

        # Case 2. no --priority is specified
        expected = self.format_error_message(
            "You must specify --priority")

        self.assert_system_exit(
            handle_set_task_priority,
            options,
            session,
            ['1'],
            stderr=expected,
            activate_session=None)
        activate_session_mock.assert_not_called()

        # Case 3 . Wrong task id (not integer format)
        for case in ['1.0', '0.1', 'abc']:
            expected = self.format_error_message(
                "Task numbers must be integers")

            self.assert_system_exit(
                handle_set_task_priority,
                options,
                session,
                [case, '--priority', '10'],
                stderr=expected,
                activate_session=None)
            activate_session_mock.assert_not_called()

        calls = [mock.call(int(tid), 10, False) for tid in arguments[2:]]
        handle_set_task_priority(options, session, arguments)
        activate_session_mock.assert_called_with(session, options)
        session.setTaskPriority.assert_has_calls(calls)
        self.assert_console_message(stdout, '')

    def test_handle_set_task_priority_help(self):
        self.assert_help(
            handle_set_task_priority,
            """Usage: %s set-task-priority [options] --priority=<priority> <task_id> [<task_id> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help           show this help message and exit
  --priority=PRIORITY  New priority
  --recurse            Change priority of child tasks as well
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
