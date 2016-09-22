import unittest

import os
import sys
import StringIO as stringio

import mock

from mock import call

import loadcli

cli = loadcli.cli


class TestWatchTasks(unittest.TestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        cli.options = self.options
        self.session = mock.MagicMock(name='sessionMock')
        self.args = mock.MagicMock()
        self.original_parser = cli.OptionParser
        cli.OptionParser = mock.MagicMock()
        self.parser = cli.OptionParser.return_value

    def tearDown(self):
        cli.OptionParser = self.original_parser

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    def test_watch_tasks_no_tasklist(self, stdout):
        returned = cli.watch_tasks(self.session, [])
        actual = stdout.getvalue()
        expected = ""
        self.assertIsNone(returned)
        self.assertEqual(actual, expected)

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    @mock.patch('koji_cli.TaskWatcher')
    @mock.patch('koji_cli._display_tasklist_status')
    @mock.patch('koji_cli._display_task_results')
    def test_watch_tasks(self, dtrMock, dtsMock, twClzMock, stdout):
        self.options.poll_interval = 0
        manager = mock.MagicMock()
        manager.attach_mock(twClzMock, 'TaskWatcherMock')
        manager.attach_mock(dtrMock, 'display_task_results_mock')
        manager.attach_mock(dtsMock, 'display_tasklist_status_mock')
        tw1 = manager.tw1
        tw1.level = 0
        tw1.is_done.side_effect = [False, True, False, True, True]
        tw1.update.side_effect = [False, False, True, True, True]
        tw1.is_success.return_value = False
        tw2 = manager.tw2
        tw2.level = 0
        tw2.is_done.side_effect = [False, False, False, False, True]
        tw2.update.side_effect = [True, False, False, True, True]
        tw2.is_success.return_value = False
        self.session.getTaskChildren.side_effect = lambda p: [
            {'id': 11}, {'id': 12}] if (0 == p) else []
        manager.attach_mock(self.session, 'sessionMock')

        def side_effect(*args, **kwargs):
            rt = None
            if args[0] not in range(2):
                rt = mock.MagicMock()
                rt.level = args[2]
                rt.is_done.return_value = True
                rt.update.return_value = True
                rt.is_success.return_value = True
                manager.attach_mock(rt, 'tw' + str(args[0]))
            else:
                rt = {0: tw1, 1: tw2}.get(args[0])
            return rt

        twClzMock.side_effect = side_effect
        rv = cli.watch_tasks(self.session, range(2), quiet=False)
        actual = stdout.getvalue()
        self.assertMultiLineEqual(
            actual, "Watching tasks (this may be safely interrupted)...\n\n")
        self.assertEqual(rv, 1)
        self.assertEqual(manager.mock_calls,
                         [call.TaskWatcherMock(0, self.session, quiet=False),
                          call.TaskWatcherMock(1, self.session, quiet=False),
                          call.tw1.update(),
                          call.tw1.is_done(),
                          call.sessionMock.getTaskChildren(0),
                          call.TaskWatcherMock(11, self.session, 1, quiet=False),
                          call.tw11.update(),
                          call.TaskWatcherMock(12, self.session, 1, quiet=False),
                          call.tw12.update(),
                          call.tw2.update(),
                          call.tw2.is_done(),
                          call.sessionMock.getTaskChildren(1),
                          call.tw1.update(),
                          call.tw1.is_done(),
                          call.tw1.is_success(),
                          call.sessionMock.getTaskChildren(0),
                          call.tw2.update(),
                          call.tw2.is_done(),
                          call.sessionMock.getTaskChildren(1),
                          call.tw11.update(),
                          call.tw11.is_done(),
                          call.display_tasklist_status_mock({0: tw1, 1: tw2, 11: manager.tw11, 12: manager.tw12}),
                          call.tw11.is_success(),
                          call.sessionMock.getTaskChildren(11),
                          call.tw12.update(),
                          call.tw12.is_done(),
                          call.display_tasklist_status_mock({0: tw1, 1: tw2, 11: manager.tw11, 12: manager.tw12}),
                          call.tw12.is_success(),
                          call.sessionMock.getTaskChildren(12),
                          call.tw1.update(),
                          call.tw1.is_done(),
                          call.sessionMock.getTaskChildren(0),
                          call.tw2.update(),
                          call.tw2.is_done(),
                          call.sessionMock.getTaskChildren(1),
                          call.tw11.update(),
                          call.tw11.is_done(),
                          call.display_tasklist_status_mock({0: tw1, 1: tw2, 11: manager.tw11, 12: manager.tw12}),
                          call.tw11.is_success(),
                          call.sessionMock.getTaskChildren(11),
                          call.tw12.update(),
                          call.tw12.is_done(),
                          call.display_tasklist_status_mock({0: tw1, 1: tw2, 11: manager.tw11, 12: manager.tw12}),
                          call.tw12.is_success(),
                          call.sessionMock.getTaskChildren(12),
                          call.tw1.update(),
                          call.tw1.is_done(),
                          call.display_tasklist_status_mock({0: tw1, 1: tw2, 11: manager.tw11, 12: manager.tw12}),
                          call.tw1.is_success(),
                          call.sessionMock.getTaskChildren(0),
                          call.tw2.update(),
                          call.tw2.is_done(),
                          call.sessionMock.getTaskChildren(1),
                          call.tw11.update(),
                          call.tw11.is_done(),
                          call.display_tasklist_status_mock({0: tw1, 1: tw2, 11: manager.tw11, 12: manager.tw12}),
                          call.tw11.is_success(),
                          call.sessionMock.getTaskChildren(11),
                          call.tw12.update(),
                          call.tw12.is_done(),
                          call.display_tasklist_status_mock({0: tw1, 1: tw2, 11: manager.tw11, 12: manager.tw12}),
                          call.tw12.is_success(),
                          call.sessionMock.getTaskChildren(12),
                          call.tw1.update(),
                          call.tw1.is_done(),
                          call.display_tasklist_status_mock({0: tw1, 1: tw2, 11: manager.tw11, 12: manager.tw12}),
                          call.tw1.is_success(),
                          call.sessionMock.getTaskChildren(0),
                          call.tw2.update(),
                          call.tw2.is_done(),
                          call.display_tasklist_status_mock({0: tw1, 1: tw2, 11: manager.tw11, 12: manager.tw12}),
                          call.tw2.is_success(),
                          call.sessionMock.getTaskChildren(1),
                          call.tw11.update(),
                          call.tw11.is_done(),
                          call.display_tasklist_status_mock({0: tw1, 1: tw2, 11: manager.tw11, 12: manager.tw12}),
                          call.tw11.is_success(),
                          call.sessionMock.getTaskChildren(11),
                          call.tw12.update(),
                          call.tw12.is_done(),
                          call.display_tasklist_status_mock({0: tw1, 1: tw2, 11: manager.tw11, 12: manager.tw12}),
                          call.tw12.is_success(),
                          call.sessionMock.getTaskChildren(12),
                          call.display_task_results_mock({0: tw1, 1: tw2, 11: manager.tw11, 12: manager.tw12})
                          ])

    @mock.patch('sys.stdout', new_callable=stringio.StringIO)
    @mock.patch('koji_cli.TaskWatcher')
    @mock.patch('koji_cli._display_tasklist_status')
    @mock.patch('koji_cli._display_task_results')
    def test_watch_tasks_with_keyboardinterrupt(
            self, dtrMock, dtsMock, twClzMock, stdout):
        """Raise KeyboardInterrupt inner watch_tasks.
        Raising it by SIGNAL might be better"""
        self.options.poll_interval = 0
        manager = mock.MagicMock()
        manager.attach_mock(twClzMock, 'TaskWatcherMock')
        manager.attach_mock(dtrMock, 'display_task_results_mock')
        manager.attach_mock(dtsMock, 'display_tasklist_status_mock')
        tw1 = manager.tw1
        tw1.level = 0
        tw1.is_done.side_effect = [False, KeyboardInterrupt, False]
        tw1.update.side_effect = [False, False]
        tw1.is_success.return_value = False
        tw1.str.return_value = 'tw1'
        tw1.display_state.return_value = 'tw1.display_state'
        tw2 = manager.tw2
        tw2.level = 0
        tw2.is_done.side_effect = [False, False, False, False, True]
        tw2.update.side_effect = [True, False, False, True, True]
        tw2.is_success.return_value = False
        tw2.str.return_value = 'tw2'
        tw2.display_state.return_value = 'tw2.display_state'
        self.session.getTaskChildren.side_effect = lambda p: [
            {'id': 11}, {'id': 12}] if (0 == p) else []
        manager.attach_mock(self.session, 'sessionMock')

        def side_effect(*args, **kwargs):
            rt = None
            if args[0] not in range(2):
                rt = mock.MagicMock()
                rt.level = args[2]
                rt.is_done.return_value = True
                rt.update.return_value = True
                rt.is_success.return_value = True
                manager.attach_mock(rt, 'tw' + str(args[0]))
            else:
                rt = {0: tw1, 1: tw2}.get(args[0])
            return rt

        twClzMock.side_effect = side_effect

        cli.watch_tasks(self.session, range(2), quiet=False)

        actual = stdout.getvalue()
        self.assertMultiLineEqual(
            actual, """Watching tasks (this may be safely interrupted)...
Tasks still running. You can continue to watch with the '%s watch-task' command.
Running Tasks:
tw1: tw1.display_state
tw2: tw2.display_state
""" % (os.path.basename(sys.argv[0]) or 'koji') )

if __name__ == '__main__':
    unittest.main()
