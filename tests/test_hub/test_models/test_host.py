from __future__ import absolute_import
import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji
import kojihub


class TestHost(unittest.TestCase):

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
        self.assertEquals(len(processor.mock_calls), 6)
        update1 = mock.call(
            'task',
            clauses=['id=%(parent)s'],
            values=mock.ANY,
        )
        self.assertEquals(processor.call_args_list[0], update1)
        update2 = mock.call(
            'task',
            clauses=['parent=%(parent)s'],
            values=mock.ANY,
        )
        self.assertEquals(processor.call_args_list[1], update2)


    @mock.patch('kojihub.UpdateProcessor')
    @mock.patch('kojihub.context')
    def test_task_set_wait_all_tasks(self, context, processor):
        host = kojihub.Host(id=1234)
        host.taskSetWait(parent=123, tasks=None)
        self.assertEquals(len(processor.mock_calls), 6)
        update1 = mock.call(
            'task',
            clauses=['id=%(parent)s'],
            values=mock.ANY,
        )
        self.assertEquals(processor.call_args_list[0], update1)
        update2 = mock.call(
            'task',
            clauses=['parent=%(parent)s'],
            values=mock.ANY,
        )
        self.assertEquals(processor.call_args_list[1], update2)

    @mock.patch('kojihub.UpdateProcessor')
    @mock.patch('kojihub.context')
    def test_task_set_wait_some_tasks(self, context, processor):
        host = kojihub.Host(id=1234)
        host.taskSetWait(parent=123, tasks=[234, 345])
        self.assertEquals(len(processor.mock_calls), 9)
        update1 = mock.call(
            'task',
            clauses=['id=%(parent)s'],
            values=mock.ANY,
        )
        self.assertEquals(processor.call_args_list[0], update1)
        update2 = mock.call(
            'task',
            clauses=['id IN %(tasks)s', 'parent=%(parent)s'],
            values=mock.ANY,
        )
        self.assertEquals(processor.call_args_list[1], update2)
        update3 = mock.call(
            'task',
            clauses=['id NOT IN %(tasks)s', 'parent=%(parent)s', 'awaited=true'],
            values=mock.ANY,
        )
        self.assertEquals(processor.call_args_list[2], update3)

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
        self.assertEquals(finished, [2, 3])
        self.assertEquals(unfinished, [1, 4])

    @mock.patch('kojihub.context')
    def test_task_wait(self, context):
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            (1, 1),
            (2, 2),
            (3, 3),
            (4, 4),
        ]
        host = kojihub.Host(id=1234)
        host.taskWait(parent=123)
        self.assertEquals(len(cursor.execute.mock_calls), 3)
