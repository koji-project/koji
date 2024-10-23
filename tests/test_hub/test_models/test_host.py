from __future__ import absolute_import
from unittest import mock
import unittest

import koji
import kojihub

UP = kojihub.UpdateProcessor
QP = kojihub.QueryProcessor


class TestHost(unittest.TestCase):

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = self.query_execute
        self.queries.append(query)
        return query

    def setUp(self):
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_execute = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('kojihub.kojihub.context')
    def test_instantiation_not_a_host(self, context):
        context.session.getHostId.return_value = None
        context.session.logged_in = True
        with self.assertRaises(koji.AuthError):
            kojihub.Host(id=None)

    @mock.patch('kojihub.kojihub.context')
    def test_instantiation_not_logged_in(self, context):
        context.session.getHostId.return_value = None
        context.session.logged_in = False
        with self.assertRaises(koji.AuthError):
            kojihub.Host()

    @mock.patch('kojihub.kojihub.context')
    def test_instantiation_logged_in_as_host(self, context):
        context.session.getHostId.return_value = 1234
        context.session.logged_in = True
        kojihub.Host(id=None)  # No exception

    @mock.patch('kojihub.kojihub.context')
    def test_verify_not_samehost(self, context):
        context.session.getHostId.return_value = 1234
        context.session.logged_in = True
        host = kojihub.Host(id=5678)
        with self.assertRaises(koji.AuthError):
            host.verify()

    @mock.patch('kojihub.kojihub.context')
    def test_verify_not_exclusive(self, context):
        host = kojihub.Host(id=1234)
        with self.assertRaises(koji.AuthError):
            host.verify()

    @mock.patch('kojihub.kojihub.UpdateProcessor')
    @mock.patch('kojihub.kojihub.context')
    def test_task_unwait(self, context, processor):
        host = kojihub.Host(id=1234)
        host.taskUnwait(parent=123)
        self.assertEqual(len(processor.mock_calls), 6)
        update1 = mock.call(
            'task',
            clauses=['id=%(parent)s'],
            values=mock.ANY,
        )
        self.assertEqual(processor.call_args_list[0], update1)
        update2 = mock.call(
            'task',
            clauses=['parent=%(parent)s'],
            values=mock.ANY,
        )
        self.assertEqual(processor.call_args_list[1], update2)

    @mock.patch('kojihub.kojihub.UpdateProcessor')
    @mock.patch('kojihub.kojihub.context')
    def test_task_set_wait_all_tasks(self, context, processor):
        host = kojihub.Host(id=1234)
        host.taskSetWait(parent=123, tasks=None)
        self.assertEqual(len(processor.mock_calls), 6)
        update1 = mock.call(
            'task',
            clauses=['id=%(parent)s'],
            values=mock.ANY,
        )
        self.assertEqual(processor.call_args_list[0], update1)
        update2 = mock.call(
            'task',
            clauses=['parent=%(parent)s'],
            values=mock.ANY,
        )
        self.assertEqual(processor.call_args_list[1], update2)

    @mock.patch('kojihub.kojihub.UpdateProcessor')
    @mock.patch('kojihub.kojihub.context')
    def test_task_set_wait_some_tasks(self, context, processor):
        host = kojihub.Host(id=1234)
        host.taskSetWait(parent=123, tasks=[234, 345])
        self.assertEqual(len(processor.mock_calls), 9)
        update1 = mock.call(
            'task',
            clauses=['id=%(parent)s'],
            values=mock.ANY,
        )
        self.assertEqual(processor.call_args_list[0], update1)
        update2 = mock.call(
            'task',
            clauses=['id IN %(tasks)s', 'parent=%(parent)s'],
            values=mock.ANY,
        )
        self.assertEqual(processor.call_args_list[1], update2)
        update3 = mock.call(
            'task',
            clauses=['id NOT IN %(tasks)s', 'parent=%(parent)s', 'awaited=true'],
            values=mock.ANY,
        )
        self.assertEqual(processor.call_args_list[2], update3)

    @mock.patch('kojihub.kojihub.context')
    def test_task_wait_check(self, context):
        self.query_execute.return_value = [{'id': 1, 'state': 1},
                                           {'id': 2, 'state': 2},
                                           {'id': 3, 'state': 3},
                                           {'id': 4, 'state': 4}, ]
        host = kojihub.Host(id=1234)
        finished, unfinished = host.taskWaitCheck(parent=123)
        self.assertEqual(finished, [2, 3])
        self.assertEqual(unfinished, [1, 4])

    @mock.patch('kojihub.kojihub.context')
    def test_task_wait(self, context):
        self.query_execute.return_value = [{'id': 1, 'state': 1},
                                           {'id': 2, 'state': 2},
                                           {'id': 3, 'state': 3},
                                           {'id': 4, 'state': 4}, ]
        kojihub.Host.return_value = 1234
        host = kojihub.Host(id=1234)
        host.taskWait(parent=123)
        self.assertEqual(len(self.updates), 2)

        data = {'awaited': False}

        update = self.updates[0]
        values = {'id': 2}
        self.assertEqual(update.table, 'task')
        self.assertEqual(update.values, values)
        self.assertEqual(update.data, data)
        self.assertEqual(update.rawdata, {})
        self.assertEqual(update.clauses, ['id=%(id)s'])

        update = self.updates[1]
        values = {'id': 3}
        self.assertEqual(update.table, 'task')
        self.assertEqual(update.values, values)
        self.assertEqual(update.data, data)
        self.assertEqual(update.rawdata, {})
        self.assertEqual(update.clauses, ['id=%(id)s'])
