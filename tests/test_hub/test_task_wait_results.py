import mock
import unittest

import kojihub


class TestTaskWaitResults(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        self.host_id = 99
        self.context.session.getHostId.return_value = self.host_id
        self.host_exports = kojihub.Host(self.host_id)
        self.host_exports.taskUnwait = mock.MagicMock()
        self.Task = mock.patch('kojihub.Task', side_effect=self.getTask).start()
        self.cnx = mock.patch('kojihub.context.cnx').start()
        self.tasks = {}

    def tearDown(self):
        mock.patch.stopall()

    def getTask(self, task_id):
        if task_id in self.tasks:
            return self.tasks[task_id]
        task = mock.MagicMock()
        task.id = task_id
        self.tasks[task_id] = task
        return task

    def test_basic(self):
        parent = 1
        task_ids = [5,6,7]
        for t in task_ids:
            task = self.getTask(t)
            task.getResult.return_value = "OK"
            task.isCanceled.return_value = False
        results = self.host_exports.taskWaitResults(parent, task_ids)
        expect = [[t, "OK"] for t in task_ids]
        self.assertEqual(results, expect)
        self.host_exports.taskUnwait.assert_called_with(parent)
