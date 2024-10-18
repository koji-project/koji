from __future__ import absolute_import
import koji
try:
    from unittest import mock
except ImportError:
    import mock
from six.moves import StringIO

from koji_cli.commands import handle_make_task
from . import utils


class TestAddNotification(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s make-task [options] <method> [<arg> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.watch_tasks_mock = mock.patch('koji_cli.commands.watch_tasks').start()
        self.watch_tasks_mock.return_value = 0
        self.task_id = 111
        self.method = 'test_method'
        self.channel = 'test-channel'
        self.priority = 1
        self.arch = 'test-arch'

    def tearDown(self):
        mock.patch.stopall()

    def test_make_task_without_args(self):
        arguments = []
        self.assert_system_exit(
            handle_make_task,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message('Please specify task method at least'),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.session.makeTask.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands._running_in_bg', return_value=True)
    def test_make_task_running_bg_without_watch(self, running_in_bg, stdout):
        arguments = ['--channel', self.channel, '--priority', self.priority, '--arch', self.arch,
                     self.method]
        self.session.makeTask.return_value = self.task_id
        rv = handle_make_task(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = "Created task id %i\n" % self.task_id
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(rv, None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.makeTask.assert_called_once_with(
            arch=self.arch, arglist=[], channel=self.channel, method=self.method,
            priority=self.priority)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    def test_make_task_not_running_bg_with_watch(self, running_in_bg, stdout):
        arguments = ['--channel', self.channel, '--priority', self.priority, '--arch', self.arch,
                     '--watch', self.method]
        task_id = 111
        self.session.makeTask.return_value = task_id
        rv = handle_make_task(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = "Created task id %i\n" % task_id
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(rv, 0)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.makeTask.assert_called_once_with(
            arch=self.arch, arglist=[], channel=self.channel, method=self.method,
            priority=self.priority)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    def test_make_task_not_running_bg_without_watch(self, running_in_bg, stdout):
        arguments = ['--channel', self.channel, '--priority', self.priority, '--arch', self.arch,
                     self.method]
        task_id = 111
        self.session.makeTask.return_value = task_id
        rv = handle_make_task(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = "Created task id %i\n" % task_id
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(rv, None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.makeTask.assert_called_once_with(
            arch=self.arch, arglist=[], channel=self.channel, method=self.method,
            priority=self.priority)
        self.watch_tasks_mock.assert_not_called()

    def test_handle_make_task_help(self):
        self.assert_help(
            handle_make_task,
            """Usage: %s make-task [options] <method> [<arg> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help           show this help message and exit
  --channel=CHANNEL    set channel
  --priority=PRIORITY  set priority
  --watch              watch the task
  --arch=ARCH          set arch
""" % self.progname)
