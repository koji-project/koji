from __future__ import absolute_import
import mock
import unittest

import koji.daemon
import koji


class TestGetNextTask(unittest.TestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.tm = koji.daemon.TaskManager(self.options, self.session)
        self.tm.readyForTask = mock.MagicMock()
        self.tm.takeTask = mock.MagicMock()
        self.time = mock.patch('time.time').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_not_ready(self):
        self.tm.readyForTask.return_value = False

        retval = self.tm.getNextTask()

        self.assertEqual(retval, False)
        self.session.host.getTasks.assert_not_called()
        self.tm.takeTask.assert_not_called()

    def test_no_tasks(self):
        self.tm.host_id = host_id = 999
        self.tm.readyForTask.return_value = True
        self.session.host.getTasks.return_value = []

        retval = self.tm.getNextTask()

        self.assertEqual(retval, False)
        self.session.host.getTasks.assert_called_once()
        self.tm.takeTask.assert_not_called()

    def test_one_good_task(self):
        self.tm.host_id = host_id = 999
        self.tm.readyForTask.return_value = True
        self.tm.tasks = {3: 'already running'}
        tasks = [
            {'id': 1, 'state': koji.TASK_STATES['FREE'], 'host_id': None},  # bad state
            {'id': 2, 'state': koji.TASK_STATES['ASSIGNED'], 'host_id': 666},  # wrong host
            {'id': 3, 'state': koji.TASK_STATES['ASSIGNED'], 'host_id': host_id},  # already in tasks
            {'id': 4, 'state': koji.TASK_STATES['ASSIGNED'], 'host_id': host_id},  # good
        ]
        self.session.host.getTasks.return_value = tasks

        retval = self.tm.getNextTask()

        self.assertEqual(retval, True)
        self.session.host.getTasks.assert_called_once()
        self.tm.takeTask.assert_called_once_with(tasks[3])


class TestTakeTask(unittest.TestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.tm = koji.daemon.TaskManager(self.options, self.session)
        self.tm.readyForTask = mock.MagicMock()
        self.tm.runTask = mock.MagicMock()
        self.tm.forkTask = mock.MagicMock()
        self.time = mock.patch('time.time').start()
        self.handler = mock.MagicMock()
        self.tm.handlers = {'fake': mock.MagicMock(return_value=self.handler)}

    def tearDown(self):
        mock.patch.stopall()

    def test_simple_fork(self):
        task = {
            'id': 4,
            'state': koji.TASK_STATES['ASSIGNED'],
            'method': 'fake',
        }
        self.handler.Foreground = False
        self.session.host.openTask.return_value = task
        self.tm.forkTask.return_value = ['PID', 'SESSION']

        retval = self.tm.takeTask(task)

        self.handler.setManager.assert_not_called()
        self.tm.runTask.assert_not_called()
        self.tm.forkTask.assert_called_once_with(self.handler)
        self.assertEqual(self.tm.pids, {4: 'PID'})
        self.assertEqual(self.tm.subsessions, {4: 'SESSION'})
        self.assertEqual(retval, True)

    def test_simple_foreground(self):
        task = {
            'id': 4,
            'state': koji.TASK_STATES['ASSIGNED'],
            'method': 'fake',
        }
        self.handler.Foreground = True
        self.session.host.openTask.return_value = task

        retval = self.tm.takeTask(task)

        self.handler.setManager.assert_called_once_with(self.tm)
        self.tm.runTask.assert_called_once_with(self.handler)
        self.tm.forkTask.assert_not_called()
        self.assertEqual(self.tm.pids, {})
        self.assertEqual(self.tm.subsessions, {})
        self.assertEqual(retval, True)


    def test_refuse_no_handler(self):
        task = {
            'id': 4,
            'state': koji.TASK_STATES['ASSIGNED'],
            'method': 'missing',
        }

        retval = self.tm.takeTask(task)

        self.assertEqual(retval, False)
        self.session.host.refuseTask.assert_called_once()
        self.session.getTaskInfo.assert_not_called()
        self.session.host.openTask.assert_not_called()
        self.tm.runTask.assert_not_called()
        self.tm.forkTask.assert_not_called()

    def test_skip_no_request(self):
        task = {
            'id': 4,
            'state': koji.TASK_STATES['ASSIGNED'],
            'method': 'fake',
        }
        self.session.getTaskInfo.return_value = {}

        retval = self.tm.takeTask(task)

        self.assertEqual(retval, False)
        self.session.host.openTask.assert_not_called()
        self.tm.runTask.assert_not_called()
        self.tm.forkTask.assert_not_called()

    def test_skip_bad_check(self):
        task = {
            'id': 4,
            'state': koji.TASK_STATES['ASSIGNED'],
            'method': 'fake',
        }
        self.handler.checkHost.side_effect = Exception('should refuse')

        retval = self.tm.takeTask(task)

        self.assertEqual(retval, False)
        self.session.host.refuseTask.assert_called_once()
        self.session.host.openTask.assert_not_called()
        self.tm.runTask.assert_not_called()
        self.tm.forkTask.assert_not_called()

    def test_open_fails(self):
        task = {
            'id': 4,
            'state': koji.TASK_STATES['ASSIGNED'],
            'method': 'fake',
        }
        self.session.host.openTask.return_value = None

        retval = self.tm.takeTask(task)

        self.assertEqual(retval, False)
        self.session.host.openTask.assert_called_once()
        self.tm.runTask.assert_not_called()
        self.tm.forkTask.assert_not_called()

    def test_set_weight_fails(self):
        task = {
            'id': 4,
            'state': koji.TASK_STATES['ASSIGNED'],
            'method': 'fake',
            'request': '...',
            'host_id': 999,
        }
        self.session.host.openTask.return_value = task
        self.session.host.setTaskWeight.side_effect = koji.ActionNotAllowed('should skip')
        task2 = task.copy()
        task2['host_id'] = 42
        self.session.getTaskInfo.side_effect = [task, task2]

        retval = self.tm.takeTask(task)

        self.assertEqual(retval, False)
        self.session.host.openTask.assert_called_once()
        self.tm.runTask.assert_not_called()
        self.tm.forkTask.assert_not_called()

    def test_set_weight_fails_state(self):
        self.tm.host_id = 999
        task = {
            'id': 4,
            'state': koji.TASK_STATES['ASSIGNED'],
            'method': 'fake',
            'request': '...',
            'host_id': self.tm.host_id,
        }
        self.session.host.openTask.return_value = task
        self.session.host.setTaskWeight.side_effect = koji.ActionNotAllowed('should skip')
        task2 = task.copy()
        task2['state'] = koji.TASK_STATES['FREE']
        self.session.getTaskInfo.side_effect = [task, task2]

        retval = self.tm.takeTask(task)

        self.assertEqual(retval, False)
        self.session.host.openTask.assert_called_once()
        self.tm.runTask.assert_not_called()
        self.tm.forkTask.assert_not_called()
