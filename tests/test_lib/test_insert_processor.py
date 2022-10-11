import mock
import unittest

import koji
import kojihub


class TestInsertProcessor(unittest.TestCase):
    def setUp(self):
        self.context_db = mock.patch('koji.db.context').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_basic_instantiation(self):
        proc = kojihub.InsertProcessor('sometable')
        actual = str(proc)
        expected = '-- incomplete update: no assigns'
        self.assertEqual(actual, expected)

    def test_to_string_with_data(self):
        proc = kojihub.InsertProcessor('sometable', data={'foo': 'bar'})
        actual = str(proc)
        expected = 'INSERT INTO sometable (foo) VALUES (%(foo)s)'
        self.assertEqual(actual, expected)

    def test_simple_execution_with_iterate(self):
        cursor = mock.MagicMock()
        self.context_db.cnx.cursor.return_value = cursor
        proc = kojihub.InsertProcessor('sometable', data={'foo': 'bar'})
        proc.execute()
        cursor.execute.assert_called_once_with(
            'INSERT INTO sometable (foo) VALUES (%(foo)s)',
            {'foo': 'bar'}, log_errors=True)

    def test_make_create(self,):
        cursor = mock.MagicMock()
        self.context_db.cnx.cursor.return_value = cursor
        self.context_db.session.assertLogin = mock.MagicMock()
        proc = kojihub.InsertProcessor('sometable', data={'foo': 'bar'})
        proc.make_create(event_id=1, user_id=2)
        self.assertEqual(proc.data['create_event'], 1)
        self.assertEqual(proc.data['creator_id'], 2)

        proc.make_create(user_id=2)
        self.assertEqual(proc.data['create_event'], self.context_db.event_id)
        self.assertEqual(proc.data['creator_id'], 2)

        proc.make_create(event_id=1)
        self.assertEqual(proc.data['create_event'], 1)
        self.assertEqual(proc.data['creator_id'], self.context_db.session.user_id)

        proc.make_create()
        self.assertEqual(proc.data['create_event'], self.context_db.event_id)
        self.assertEqual(proc.data['creator_id'], self.context_db.session.user_id)

    def test_dup_check(self):
        cursor = mock.MagicMock()
        self.context_db.cnx.cursor.return_value = cursor
        self.context_db.session.assertLogin = mock.MagicMock()
        proc = kojihub.InsertProcessor('sometable', data={'foo': 'bar'})
        proc.dup_check()

        args = cursor.execute.call_args
        actual = ' '.join(args[0][0].split())
        expected = 'SELECT foo FROM sometable WHERE (foo = %(foo)s)'
        self.assertEqual(actual, expected)

        proc.make_create()
        proc.dup_check()
        args = cursor.execute.call_args
        actual = ' '.join(args[0][0].split())
        expected = 'SELECT active, foo FROM sometable WHERE ' + \
            '(active = %(active)s) AND (foo = %(foo)s)'
        self.assertEqual(actual, expected)

        proc.set(onething='another')
        proc.rawset(something='something else')
        result = proc.dup_check()
        self.assertEqual(result, None)

    def test_raw_data(self):
        cursor = mock.MagicMock()
        self.context_db.cnx.cursor.return_value = cursor
        proc = kojihub.InsertProcessor('sometable', rawdata={'foo': '\'bar\''})
        result = proc.dup_check()
        self.assertEqual(result, None)
        actual = str(proc)
        expected = "INSERT INTO sometable (foo) VALUES (('bar'))"  # raw data
        self.assertEqual(actual, expected)


class TestBulkInsertProcessor(unittest.TestCase):
    def setUp(self):
        self.context_db = mock.patch('koji.db.context').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_basic_instantiation(self):
        proc = kojihub.BulkInsertProcessor('sometable')
        actual = str(proc)
        expected = '-- incomplete insert: no data'
        self.assertEqual(actual, expected)

    def test_to_string_with_single_row(self):
        proc = kojihub.BulkInsertProcessor('sometable', data=[{'foo': 'bar'}])
        actual = str(proc)
        expected = 'INSERT INTO sometable (foo) VALUES (%(foo0)s)'
        self.assertEqual(actual, expected)

        proc = kojihub.BulkInsertProcessor('sometable')
        proc.add_record(foo='bar')
        actual = str(proc)
        self.assertEqual(actual, expected)

    def test_simple_execution(self):
        cursor = mock.MagicMock()
        self.context_db.cnx.cursor.return_value = cursor
        proc = kojihub.BulkInsertProcessor('sometable', data=[{'foo': 'bar'}])
        proc.execute()
        cursor.execute.assert_called_once_with(
            'INSERT INTO sometable (foo) VALUES (%(foo0)s)',
            {'foo0': 'bar'},
            log_errors=True
        )

        cursor.reset_mock()
        proc = kojihub.BulkInsertProcessor('sometable')
        proc.add_record(foo='bar')
        proc.execute()
        cursor.execute.assert_called_once_with(
            'INSERT INTO sometable (foo) VALUES (%(foo0)s)',
            {'foo0': 'bar'},
            log_errors=True
        )

    def test_bulk_execution(self):
        cursor = mock.MagicMock()
        self.context_db.cnx.cursor.return_value = cursor

        proc = kojihub.BulkInsertProcessor('sometable', data=[{'foo': 'bar1'}])
        proc.add_record(foo='bar2')
        proc.add_record(foo='bar3')
        proc.execute()
        cursor.execute.assert_called_once_with(
            'INSERT INTO sometable (foo) VALUES (%(foo0)s), (%(foo1)s), (%(foo2)s)',
            {'foo0': 'bar1', 'foo1': 'bar2', 'foo2': 'bar3'},
            log_errors=True
        )

    def test_missing_values(self):
        proc = kojihub.BulkInsertProcessor('sometable')
        proc.add_record(foo='bar')
        proc.add_record(foo2='bar2')
        with self.assertRaises(koji.GenericError) as cm:
            str(proc)
        self.assertEqual(cm.exception.args[0], 'Missing value foo2 in BulkInsert')

    def test_missing_values_nostrict(self):
        proc = kojihub.BulkInsertProcessor('sometable', strict=False)
        proc.add_record(foo='bar')
        proc.add_record(foo2='bar2')
        actual = str(proc)
        expected = 'INSERT INTO sometable (foo, foo2) VALUES (%(foo0)s, NULL), (NULL, %(foo21)s)'
        self.assertEqual(actual, expected)

    def test_missing_values_explicit_columns(self):
        proc = kojihub.BulkInsertProcessor('sometable', strict=True, columns=['foo', 'foo2'])
        proc.add_record(foo='bar')
        with self.assertRaises(koji.GenericError) as cm:
            str(proc)
        self.assertEqual(cm.exception.args[0], 'Missing value foo2 in BulkInsert')

    def test_batch_execution(self):
        cursor = mock.MagicMock()
        self.context_db.cnx.cursor.return_value = cursor

        proc = kojihub.BulkInsertProcessor('sometable', data=[{'foo': 'bar1'}], batch=2)
        proc.add_record(foo='bar2')
        proc.add_record(foo='bar3')
        proc.execute()
        calls = cursor.execute.mock_calls
        # list of (name, positional args, keyword args)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0],
                         mock.call('INSERT INTO sometable (foo) VALUES (%(foo0)s), (%(foo1)s)',
                         {'foo0': 'bar1', 'foo1': 'bar2'}, log_errors=True))
        self.assertEqual(calls[1],
                         mock.call('INSERT INTO sometable (foo) VALUES (%(foo0)s)',
                                   {'foo0': 'bar3'}, log_errors=True))

    def test_no_batch_execution(self):
        cursor = mock.MagicMock()
        self.context_db.cnx.cursor.return_value = cursor

        proc = kojihub.BulkInsertProcessor('sometable', data=[{'foo': 'bar1'}], batch=0)
        proc.add_record(foo='bar2')
        proc.add_record(foo='bar3')
        proc.execute()
        calls = cursor.execute.mock_calls
        # list of (name, positional args, keyword args)
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0],
            mock.call('INSERT INTO sometable (foo) VALUES (%(foo0)s), (%(foo1)s), (%(foo2)s)',
                      {'foo0': 'bar1', 'foo1': 'bar2', 'foo2': 'bar3'}, log_errors=True)
        )
