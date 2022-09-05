from __future__ import absolute_import
import mock
import unittest

import koji
import kojihub

UP = kojihub.UpdateProcessor


class TestHost(unittest.TestCase):

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.UpdateProcessor = mock.patch('kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []

    @mock.patch('kojihub.context')
    def test_instantiation_not_a_host(self, context):
        context.session.getHostId.return_value = None
        context.session.logged_in = True
        with self.assertRaises(koji.AuthError):
            kojihub.Host(id=None)

    @mock.patch('kojihub.context')
    def test_instantiation_not_logged_in(self, context):
        context.session.getHostId.return_value = None
        context.session.logged_in = False
        with self.assertRaises(koji.AuthError):
            kojihub.Host()

    @mock.patch('kojihub.context')
    def test_instantiation_logged_in_as_host(self, context):
        context.session.getHostId.return_value = 1234
        context.session.logged_in = True
        kojihub.Host(id=None)  # No exception

    @mock.patch('kojihub.context')
    def test_verify_not_samehost(self, context):
        context.session.getHostId.return_value = 1234
        context.session.logged_in = True
        host = kojihub.Host(id=5678)
        with self.assertRaises(koji.AuthError):
            host.verify()

    @mock.patch('kojihub.context')
    def test_verify_not_exclusive(self, context):
        host = kojihub.Host(id=1234)
        with self.assertRaises(koji.AuthError):
            host.verify()

    @mock.patch('kojihub.UpdateProcessor')
    @mock.patch('kojihub.context')
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

    @mock.patch('kojihub.UpdateProcessor')
    @mock.patch('kojihub.context')
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

    @mock.patch('kojihub.UpdateProcessor')
    @mock.patch('kojihub.context')
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

    @mock.patch('kojihub.context')
    def test_task_wait_check(self, context):
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            (1, 1),
            (2, 2),
            (3, 3),
            (4, 4),
        ]
        host = kojihub.Host(id=1234)
        finished, unfinished = host.taskWaitCheck(parent=123)
        cursor.execute.assert_called_once()
        self.assertEqual(finished, [2, 3])
        self.assertEqual(unfinished, [1, 4])

    @mock.patch('kojihub.context')
    def test_task_wait(self, context):
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor
        context.session.assertLogin = mock.MagicMock()
        cursor.fetchall.return_value = [
            (1, 1),
            (2, 2),
            (3, 3),
            (4, 4),
        ]
        context.event_id = 42
        context.session.user_id = 23
        kojihub.Host.return_value = 1234
        host = kojihub.Host(id=1234)
        host.taskWait(parent=123)
        self.assertEqual(len(self.updates), 2)
        self.assertEqual(len(cursor.execute.mock_calls), 1)

        rawdata = {'awaited': 'false'}

        update = self.updates[0]
        values = {'id': 2}
        self.assertEqual(update.table, 'task')
        self.assertEqual(update.values, values)
        self.assertEqual(update.data, {})
        self.assertEqual(update.rawdata, rawdata)
        self.assertEqual(update.clauses, ['id=%(id)s'])

        update = self.updates[1]
        values = {'id': 3}
        self.assertEqual(update.table, 'task')
        self.assertEqual(update.values, values)
        self.assertEqual(update.data, {})
        self.assertEqual(update.rawdata, rawdata)
        self.assertEqual(update.clauses, ['id=%(id)s'])
