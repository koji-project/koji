import mock
import xmlrpc.client
import unittest

import koji
import kojihub


QP = kojihub.QueryProcessor


class TestTaskWaitResults(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        self.host_id = 99
        self.context.session.getHostId.return_value = self.host_id
        self.host_exports = kojihub.Host(self.host_id)
        self.host_exports.taskUnwait = mock.MagicMock()
        self.Task = mock.patch('kojihub.Task', side_effect=self.getTask).start()
        self.tasks = {}
        self.queries = []
        self.execute = mock.MagicMock()
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
            side_effect=self.get_query).start()

    def tearDown(self):
        mock.patch.stopall()

    def getTask(self, task_id):
        if task_id in self.tasks:
            return self.tasks[task_id]
        task = mock.MagicMock()
        task.id = task_id
        self.tasks[task_id] = task
        return task

    def get_query(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = self.execute
        self.queries.append(query)
        return query

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
        self.assertEqual(self.queries, [])
        self.host_exports.taskUnwait.assert_called_with(parent)

    def test_error(self):
        """Ensure that errors is propagated when they should be"""
        parent = 1
        task_ids = [5,6,7]
        for t in task_ids:
            task = self.getTask(t)
            task.getResult.return_value = "OK"
            task.isCanceled.return_value = False
        self.tasks[6].getResult.side_effect = xmlrpc.client.Fault(1, "error")
        with self.assertRaises(xmlrpc.client.Fault):
            results = self.host_exports.taskWaitResults(parent, task_ids)
            self.assertEqual(results, [])
        self.tasks[6].getResult.side_effect = koji.GenericError('problem')
        with self.assertRaises(koji.GenericError):
            results = self.host_exports.taskWaitResults(parent, task_ids)
            self.assertEqual(results, [])
        self.assertEqual(self.queries, [])

    def test_canfail_canceled(self):
        """Canceled canfail tasks should not raise exceptions"""
        parent = 1
        task_ids = [5,6,7]
        canfail = [7]
        for t in task_ids:
            task = self.getTask(t)
            task.getResult.return_value = "OK"
            task.isCanceled.return_value = False
        self.tasks[7].getResult.side_effect = koji.GenericError('canceled')
        self.tasks[7].isCanceled.return_value = True
        results = self.host_exports.taskWaitResults(parent, task_ids,
                        canfail=canfail)
        expect_f = {'faultCode': koji.GenericError.faultCode,
                    'faultString': 'canceled'}
        expect = [[5, "OK"], [6, "OK"], [7, expect_f]]
        self.assertEqual(results, expect)
        self.host_exports.taskUnwait.assert_called_with(parent)
        self.assertEqual(self.queries, [])

    def test_all_tasks(self):
        """Canceled canfail tasks should not raise exceptions"""
        parent = 1
        task_ids = [5,6,7]
        self.execute.return_value = [[t] for t in task_ids]
        for t in task_ids:
            task = self.getTask(t)
            task.getResult.return_value = "OK"
            task.isCanceled.return_value = False
        results = self.host_exports.taskWaitResults(parent, None)
        expect = [[t, "OK"] for t in task_ids]
        self.assertEqual(results, expect)
        self.host_exports.taskUnwait.assert_called_with(parent)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['task'])
        self.assertEqual(query.columns, ['id'])
