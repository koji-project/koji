from __future__ import absolute_import
import json
try:
    from unittest import mock
except ImportError:
    import mock
import os
import six
import sys
import unittest

from six.moves import StringIO

import koji
from koji_cli.lib import watch_tasks
from koji_cli.commands import anon_handle_watch_task
from .fakeclient import FakeClientSession, RecordingClientSession
from . import utils


class TestWatchTasksCliLib(unittest.TestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = FakeClientSession('SERVER', {})
        self.recording = False
        self.record_file = None
        self.args = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()
        if self.recording:
            # save recorded calls
            if self.record_file:
                koji.dump_json(self.record_file, self.session.get_calls())
            else:
                json.dump(self.session.get_calls(), sys.stderr, indent=4)
            self.recording = False
            self.record_file = None

    def setup_record(self, filename=None):
        self.session = RecordingClientSession('http://localhost/kojihub', {})
        self.recording = True
        self.record_file = filename

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_watch_tasks_no_tasklist(self, stdout):
        returned = watch_tasks(self.session, [], poll_interval=0, topurl=self.options.topurl)
        actual = stdout.getvalue()
        expected = ""
        self.assertIsNone(returned)
        self.assertEqual(actual, expected)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_watch_tasks(self, stdout):
        # self.setup_record('foo.json')
        cfile = os.path.dirname(__file__) + '/data/calls/watchtasks1.json'
        cdata = koji.load_json(cfile)
        self.session.load_calls(cdata)
        rv = watch_tasks(self.session, [1188], quiet=False, poll_interval=0,
                         topurl=self.options.topurl)
        self.assertEqual(rv, 0)
        expected = ('''Watching tasks (this may be safely interrupted)...
1188 build (f24, /users/mikem/fake.git:adaf62586b4b4a23b24394da5586abd7cd9f679e): closed
  1189 buildSRPMFromSCM (/users/mikem/fake.git:adaf62586b4b4a23b24394da5586abd7cd9f679e): closed
  1190 buildArch (fake-1.1-21.src.rpm, noarch): closed

1188 build (f24, /users/mikem/fake.git:adaf62586b4b4a23b24394da5586abd7cd9f679e) completed successfully
''')
        self.assertMultiLineEqual(stdout.getvalue(), expected)

    @mock.patch('time.sleep')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_watch_tasks_fail(self, stdout, sleep):
        # self.setup_record('foo.json')
        cfile = os.path.dirname(__file__) + '/data/calls/watchtasks2.json'
        cdata = koji.load_json(cfile)
        self.session.load_calls(cdata)
        rv = watch_tasks(self.session, [1208], quiet=False, poll_interval=5, topurl=None)
        self.assertEqual(rv, 1)
        expected = ('''Watching tasks (this may be safely interrupted)...
1208 build (f24, /users/mikem/fake.git:master): free
1208 build (f24, /users/mikem/fake.git:master): free -> open (builder-01)
  1209 buildSRPMFromSCM (/users/mikem/fake.git:master): free
  1209 buildSRPMFromSCM (/users/mikem/fake.git:master): free -> open (builder-01)
1208 build (f24, /users/mikem/fake.git:master): open (builder-01) -> FAILED: GenericError: Build already exists (id=425, state=COMPLETE): {'name': 'fake', 'task_id': 1208, 'extra': None, 'pkg_id': 298, 'epoch': 7, 'completion_time': None, 'state': 0, 'version': '1.1', 'source': None, 'volume_id': 0, 'owner': 1, 'release': '22', 'start_time': 'NOW'}
  0 free  1 open  0 done  1 failed
  1209 buildSRPMFromSCM (/users/mikem/fake.git:master): open (builder-01) -> closed
  0 free  0 open  1 done  1 failed

1208 build (f24, /users/mikem/fake.git:master) failed
''')
        self.assertMultiLineEqual(stdout.getvalue(), expected)

    @mock.patch('time.sleep')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_watch_tasks_with_keyboardinterrupt(self, stdout, sleep):
        """Raise KeyboardInterrupt inner watch_tasks.
        Raising it by SIGNAL might be better"""
        cfile = os.path.dirname(__file__) + '/data/calls/watchtasks2.json'
        cdata = koji.load_json(cfile)
        self.session.load_calls(cdata)
        sleep.side_effect = [None] * 10 + [KeyboardInterrupt]
        with self.assertRaises(KeyboardInterrupt):
            # watch_tasks catches and re-raises it to display a message
            watch_tasks(self.session, [1208], quiet=False, poll_interval=5,
                        topurl=self.options.topurl)
        expected = ('''Watching tasks (this may be safely interrupted)...
1208 build (f24, /users/mikem/fake.git:master): free
1208 build (f24, /users/mikem/fake.git:master): free -> open (builder-01)
  1209 buildSRPMFromSCM (/users/mikem/fake.git:master): free
  1209 buildSRPMFromSCM (/users/mikem/fake.git:master): free -> open (builder-01)
Tasks still running. You can continue to watch with the '%s watch-task' command.
Running Tasks:
1208 build (f24, /users/mikem/fake.git:master): open (builder-01)
  1209 buildSRPMFromSCM (/users/mikem/fake.git:master): open (builder-01)
''' % (os.path.basename(sys.argv[0]) or 'koji'))
        self.assertMultiLineEqual(stdout.getvalue(), expected)

    @mock.patch('time.sleep')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_watch_tasks_with_keyboardinterrupt_handler(self, stdout, sleep):
        """Raise KeyboardInterrupt inner watch_tasks with a ki_handler"""
        cfile = os.path.dirname(__file__) + '/data/calls/watchtasks2.json'
        cdata = koji.load_json(cfile)
        self.session.load_calls(cdata)
        sleep.side_effect = [None] * 10 + [KeyboardInterrupt]

        def customized_handler(progname, tasks, quiet):
            print('some output')

        with self.assertRaises(KeyboardInterrupt):
            # watch_tasks catches and re-raises it to display a message
            watch_tasks(self.session, [1208], quiet=False, poll_interval=5,
                        ki_handler=customized_handler, topurl=self.options.topurl)
        expected = ('''Watching tasks (this may be safely interrupted)...
1208 build (f24, /users/mikem/fake.git:master): free
1208 build (f24, /users/mikem/fake.git:master): free -> open (builder-01)
  1209 buildSRPMFromSCM (/users/mikem/fake.git:master): free
  1209 buildSRPMFromSCM (/users/mikem/fake.git:master): free -> open (builder-01)
some output
''')
        self.assertMultiLineEqual(stdout.getvalue(), expected)


class TestWatchLogsCLI(utils.CliTestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.ensure_connection = mock.patch('koji_cli.commands.ensure_connection').start()
        self.list_tasks = mock.patch('koji_cli.commands._list_tasks').start()
        self.error_format = """Usage: %s watch-task [options] <task id> [<task id> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_watch_task_help(self):
        self.assert_help(
            anon_handle_watch_task,
            """Usage: %s watch-task [options] <task id> [<task id> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help         show this help message and exit
  --quiet            Do not print the task information
  --mine             Just watch your tasks
  --user=USER        Only tasks for this user
  --arch=ARCH        Only tasks for this architecture
  --method=METHOD    Only tasks of this method
  --channel=CHANNEL  Only tasks in this channel
  --host=HOST        Only tasks for this host
""" % self.progname)

    def test_watch_task_selection_and_task_id(self):
        for arg in ['--mine', '--user=kojiadmin', '--arch=test-arcg', '--method=build',
                    '--channel=default', '--host=test-host']:
            arguments = [arg, '1']
            self.assert_system_exit(
                anon_handle_watch_task,
                self.options, self.session, arguments,
                stdout='',
                stderr=self.format_error_message("Selection options cannot be combined with a task list"),
                exit_code=2,
                activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.ensure_connection.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_watch_task_mine_without_task(self, stdout):
        expected_output = "(no tasks)\n"
        self.list_tasks.return_value = []
        anon_handle_watch_task(self.options, self.session, ['--mine'])
        self.assert_console_message(stdout, expected_output)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.ensure_connection.assert_not_called()

    def test_watch_task_task_id_not_int(self):
        arguments = ['task-id']
        self.assert_system_exit(
            anon_handle_watch_task,
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
            anon_handle_watch_task,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("at least one task id must be specified"),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.ensure_connection.assert_called_once_with(self.session, self.options)


if __name__ == '__main__':
    unittest.main()
