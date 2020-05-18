import mock
import unittest

import koji
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


class TestBulkInsertProcessor(unittest.TestCase):
    def test_basic_instantiation(self):
        proc = kojihub.BulkInsertProcessor('sometable')
        actual = str(proc)
        expected = '-- incomplete insert: no data'
        self.assertEquals(actual, expected)

    def test_to_string_with_single_row(self):
        proc = kojihub.BulkInsertProcessor('sometable', data=[{'foo': 'bar'}])
        actual = str(proc)
        expected = 'INSERT INTO sometable (foo) VALUES (%(foo0)s)'
        self.assertEquals(actual, expected)

        proc = kojihub.BulkInsertProcessor('sometable')
        proc.add_record(foo='bar')
        actual = str(proc)
        self.assertEquals(actual, expected)

    @mock.patch('kojihub.context')
    def test_simple_execution(self, context):
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor
        proc = kojihub.BulkInsertProcessor('sometable', data=[{'foo': 'bar'}])
        proc.execute()
        cursor.execute.assert_called_once_with(
            'INSERT INTO sometable (foo) VALUES (%(foo0)s)',
            {'foo0': 'bar'},
        )

        cursor.reset_mock()
        proc = kojihub.BulkInsertProcessor('sometable')
        proc.add_record(foo='bar')
        proc.execute()
        cursor.execute.assert_called_once_with(
            'INSERT INTO sometable (foo) VALUES (%(foo0)s)',
            {'foo0': 'bar'},
        )

    @mock.patch('kojihub.context')
    def test_bulk_execution(self, context):
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor

        proc = kojihub.BulkInsertProcessor('sometable', data=[{'foo': 'bar1'}])
        proc.add_record(foo='bar2')
        proc.add_record(foo='bar3')
        proc.execute()
        cursor.execute.assert_called_once_with(
            'INSERT INTO sometable (foo) VALUES (%(foo0)s), (%(foo1)s), (%(foo2)s)',
            {'foo0': 'bar1', 'foo1': 'bar2', 'foo2': 'bar3'},
        )

    def test_missing_values(self):
        proc = kojihub.BulkInsertProcessor('sometable')
        proc.add_record(foo='bar')
        proc.add_record(foo2='bar2')
        with self.assertRaises(koji.GenericError) as cm:
            str(proc)
        self.assertEquals(cm.exception.args[0], 'Missing value foo2 in BulkInsert')

    def test_missing_values_nostrict(self):
        proc = kojihub.BulkInsertProcessor('sometable', strict=False)
        proc.add_record(foo='bar')
        proc.add_record(foo2='bar2')
        actual = str(proc)
        expected = 'INSERT INTO sometable (foo, foo2) VALUES (%(foo0)s, NULL), (NULL, %(foo21)s)'
        self.assertEquals(actual, expected)

    def test_missing_values_explicit_columns(self):
        proc = kojihub.BulkInsertProcessor('sometable', strict=True, columns=['foo', 'foo2'])
        proc.add_record(foo='bar')
        with self.assertRaises(koji.GenericError) as cm:
            str(proc)
        self.assertEquals(cm.exception.args[0], 'Missing value foo2 in BulkInsert')

    @mock.patch('kojihub.context')
    def test_batch_execution(self, context):
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor

        proc = kojihub.BulkInsertProcessor('sometable', data=[{'foo': 'bar1'}], batch=2)
        proc.add_record(foo='bar2')
        proc.add_record(foo='bar3')
        proc.execute()
        calls = cursor.execute.mock_calls
        # list of (name, positional args, keyword args)
        self.assertEquals(len(calls), 2)
        self.assertEquals(
                calls[0][1],
                ('INSERT INTO sometable (foo) VALUES (%(foo0)s), (%(foo1)s)',
                    {'foo0': 'bar1', 'foo1': 'bar2'}))
        self.assertEquals(
                calls[1][1],
                ('INSERT INTO sometable (foo) VALUES (%(foo0)s)',
                    {'foo0': 'bar3'}))

    @mock.patch('kojihub.context')
    def test_no_batch_execution(self, context):
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor

        proc = kojihub.BulkInsertProcessor('sometable', data=[{'foo': 'bar1'}], batch=None)
        proc.add_record(foo='bar2')
        proc.add_record(foo='bar3')
        proc.execute()
        calls = cursor.execute.mock_calls
        # list of (name, positional args, keyword args)
        self.assertEquals(len(calls), 1)
        self.assertEquals(
                calls[0][1],
                ('INSERT INTO sometable (foo) VALUES (%(foo0)s), (%(foo1)s), (%(foo2)s)',
                    {'foo0': 'bar1', 'foo1': 'bar2', 'foo2': 'bar3'}))
