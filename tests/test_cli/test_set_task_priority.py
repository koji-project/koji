from __future__ import absolute_import
try:
    from unittest import mock
except ImportError:
    import mock
import six
import unittest

from koji_cli.commands import handle_set_task_priority

import koji
from . import utils


class TestSetTaskPriority(utils.CliTestCase):

    def setUp(self):
        # Show long diffs in error output...
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s set-task-priority [options] --priority=<priority> <task_id> [<task_id> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_set_task_priority(self, stdout, stderr):
        """Test handle_set_task_priority function"""
        arguments = ['--priority', '10', '1', '11', '121', '1331']

        # Case 1. no task id error
        self.assert_system_exit(
            handle_set_task_priority,
            self.options, self.session, [],
            stderr=self.format_error_message("You must specify at least one task id"),
            activate_session=None)
        self.activate_session_mock.assert_not_called()

        # Case 2. no --priority is specified
        self.assert_system_exit(
            handle_set_task_priority,
            self.options, self.session, ['1'],
            stderr=self.format_error_message("You must specify --priority"),
            activate_session=None)
        self.activate_session_mock.assert_not_called()

        # Case 3 . Wrong task id (not integer format)
        for case in ['1.0', '0.1', 'abc']:
            self.assert_system_exit(
                handle_set_task_priority,
                self.options, self.session, [case, '--priority', '10'],
                stderr=self.format_error_message("Task numbers must be integers"),
                activate_session=None)
            self.activate_session_mock.assert_not_called()

        calls = [mock.call(int(tid), 10, False) for tid in arguments[2:]]
        handle_set_task_priority(self.options, self.session, arguments)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.setTaskPriority.assert_has_calls(calls)
        self.assert_console_message(stdout, '')

        # Case 4. User doesn't have admin perm
        self.session.hasPerm.return_value = False
        self.session.getLoggedInUser.return_value = {
            'authtype': 2,
            'id': 1,
            'krb_principal': None,
            'krb_principals': [],
            'name': 'testuser',
            'status': 0,
            'usertype': 0
        }
        self.assert_system_exit(
            handle_set_task_priority,
            self.options, self.session, ['--priority', '10', '1', '2'],
            stderr="admin permission required (logged in as testuser)\n",
            activate_session=None,
            exit_code=1)

        # Case 5. Task is closed
        self.session.hasPerm.return_value = True
        self.session.setTaskPriority.side_effect = koji.GenericError
        expected_warn = "Can't update task priority on closed task: 1\n"
        handle_set_task_priority(self.options, self.session, ['--priority', '10', '1'])
        self.assert_console_message(stderr, expected_warn)

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
