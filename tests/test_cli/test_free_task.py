from __future__ import absolute_import
try:
    from unittest import mock
except ImportError:
    import mock
from six.moves import StringIO

from koji_cli.commands import handle_free_task
from . import utils


class TestFreeTask(utils.CliTestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        self.maxDiff = None
        self.session = mock.MagicMock()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s free-task [options] <task_id> [<task_id> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    def test_free_task_without_arg(self):
        expected = self.format_error_message('please specify at least one task_id')
        self.assert_system_exit(
            handle_free_task,
            self.options, self.session, [],
            stdout='',
            stderr=expected,
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.freeTask.assert_not_called()

    def test_free_task_id_string_chars(self):
        expected = self.format_error_message('task_id must be an integer')
        self.assert_system_exit(
            handle_free_task,
            self.options, self.session, ['1abc'],
            stdout='',
            stderr=expected,
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.freeTask.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_free_task_valid(self, stdout):
        self.session.freeTask.side_effect = [True, True, True]
        handle_free_task(self.options, self.session, ['1', '2', '3'])
        self.assert_console_message(stdout, '')
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.freeTask.assert_has_calls([mock.call(1), mock.call(2), mock.call(3)])

    def test_handle_free_task_help(self):
        self.assert_help(
            handle_free_task,
            """Usage: %s free-task [options] <task_id> [<task_id> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)
