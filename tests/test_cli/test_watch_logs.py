from __future__ import absolute_import
import mock
import unittest
from six.moves import StringIO

from koji_cli.commands import anon_handle_watch_logs
from . import utils


class TestWatchLogs(utils.CliTestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.ensure_connection = mock.patch('koji_cli.commands.ensure_connection').start()
        self.list_tasks = mock.patch('koji_cli.commands._list_tasks').start()
        self.error_format = """Usage: %s watch-logs [options] <task id> [<task id> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def test_handle_watch_logs_help(self):
        self.assert_help(
            anon_handle_watch_logs,
            """Usage: %s watch-logs [options] <task id> [<task id> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help    show this help message and exit
  --log=LOG     Watch only a specific log
  --mine        Watch logs for all your tasks, task_id arguments are forbidden
                in this case.
  -f, --follow  Follow spawned child tasks
""" % self.progname)

    def test_watch_task_mine_and_task_id(self):
        arguments = ['--mine', '1']
        self.assert_system_exit(
            anon_handle_watch_logs,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message(
                "Selection options cannot be combined with a task list"),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.ensure_connection.assert_not_called()

    def test_watch_task_task_id_not_int(self):
        arguments = ['task-id']
        self.assert_system_exit(
            anon_handle_watch_logs,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("task id must be an integer"),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.ensure_connection.assert_called_once_with(self.session, self.options)

    def test_watch_task_without_task(self):
        arguments = []
        self.assert_system_exit(
            anon_handle_watch_logs,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("at least one task id must be specified"),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.ensure_connection.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_watch_task_mine_without_tasks(self, stdout):
        expected_output = "You've no active tasks.\n"
        self.list_tasks.return_value = []
        anon_handle_watch_logs(self.options, self.session, ['--mine'])
        self.assert_console_message(stdout, expected_output)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.ensure_connection.assert_not_called()


if __name__ == '__main__':
    unittest.main()
