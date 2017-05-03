from __future__ import absolute_import
import unittest
import mock

import kojihub


class TestInsertProcessor(unittest.TestCase):

    def test_basic_instantiation(self):
        proc = kojihub.InsertProcessor('sometable')
        actual = str(proc)
        expected = '-- incomplete update: no assigns'
        self.assertEquals(actual, expected)

    def test_to_string_with_data(self):
        proc = kojihub.InsertProcessor('sometable', data={'foo': 'bar'})
        actual = str(proc)
        expected = 'INSERT INTO sometable (foo) VALUES (%(foo)s)'
        self.assertEquals(actual, expected)

    @mock.patch('kojihub.context')
    def test_simple_execution_with_iterate(self, context):
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor
        proc = kojihub.InsertProcessor('sometable', data={'foo': 'bar'})
        proc.execute()
        cursor.execute.assert_called_once_with(
            'INSERT INTO sometable (foo) VALUES (%(foo)s)',
            {'foo': 'bar'},
        )

    @mock.patch('kojihub.context')
    def test_make_create(self, context):
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor
        context.session.assertLogin = mock.MagicMock()
        proc = kojihub.InsertProcessor('sometable', data={'foo': 'bar'})
        proc.make_create(event_id=1, user_id=2)
        self.assertEquals(proc.data['create_event'], 1)
        self.assertEquals(proc.data['creator_id'], 2)

        proc.make_create(user_id=2)
        self.assertEquals(proc.data['create_event'], context.event_id)
        self.assertEquals(proc.data['creator_id'], 2)

        proc.make_create(event_id=1)
        self.assertEquals(proc.data['create_event'], 1)
        self.assertEquals(proc.data['creator_id'], context.session.user_id)

        proc.make_create()
        self.assertEquals(proc.data['create_event'], context.event_id)
        self.assertEquals(proc.data['creator_id'], context.session.user_id)

    @mock.patch('kojihub.context')
    def test_dup_check(self, context):
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor
        context.session.assertLogin = mock.MagicMock()
        proc = kojihub.InsertProcessor('sometable', data={'foo': 'bar'})
        proc.dup_check()

        args = cursor.execute.call_args
        actual = ' '.join(args[0][0].split())
        expected = 'SELECT foo FROM sometable WHERE (foo = %(foo)s)'
        self.assertEquals(actual, expected)

        proc.make_create()
        proc.dup_check()
        args = cursor.execute.call_args
        actual = ' '.join(args[0][0].split())
        expected = 'SELECT active, foo FROM sometable WHERE ' + \
            '(active = %(active)s) AND (foo = %(foo)s)'
        self.assertEquals(actual, expected)

        proc.set(onething='another')
        proc.rawset(something='something else')
        result = proc.dup_check()
        self.assertEquals(result, None)

    @mock.patch('kojihub.context')
    def test_raw_data(self, context):
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor
        proc = kojihub.InsertProcessor('sometable', rawdata={'foo': '\'bar\''})
        result = proc.dup_check()
        self.assertEquals(result, None)
        actual = str(proc)
        expected = "INSERT INTO sometable (foo) VALUES (('bar'))"  # raw data
        self.assertEquals(actual, expected)
