import mock
import unittest

import kojihub


class TestQueryProcessor(unittest.TestCase):
    def setUp(self):
        self.simple_arguments = dict(
            columns=['something'],
            tables=['awesome'],
        )
        self.complex_arguments = dict(
            columns=['something'],
            aliases=['other'],
            tables=['awesome'],
            joins=['morestuff'],
            #values=...
            #transform=...
            opts={
                #'countOnly': True,
                'order': 'other',
                'offset': 10,
                'limit': 3,
                'group': 'awesome.aha'
                #'rowlock': True,
            },
            enable_group=True
        )
        self.original_chunksize = kojihub.QueryProcessor.iterchunksize
        kojihub.QueryProcessor.iterchunksize = 2

    def tearDown(self):
        kojihub.QueryProcessor.iterchunksize = self.original_chunksize

    def test_basic_instantiation(self):
        kojihub.QueryProcessor()  # No exception!

    def test_instantiation_with_cols_and_aliases(self):
        proc = kojihub.QueryProcessor(columns=['wat'], aliases=['zap'])
        assert 'zap' in proc.colsByAlias
        assert proc.colsByAlias['zap'] == 'wat'
        assert len(proc.colsByAlias) == 1

    def test_empty_as_string(self):
        proc = kojihub.QueryProcessor()
        actual = str(proc)
        self.assertIn("SELECT", actual)
        self.assertIn("FROM", actual)

    def test_simple_as_string(self):
        proc = kojihub.QueryProcessor(
            columns=['something'],
            tables=['awesome'],
        )
        actual = " ".join([token for token in str(proc).split() if token])
        expected = "SELECT something FROM awesome"
        self.assertEqual(actual, expected)

    def test_complex_as_string(self):
        proc = kojihub.QueryProcessor(**self.complex_arguments)
        actual = " ".join([token for token in str(proc).split() if token])
        expected = "SELECT something FROM awesome JOIN morestuff" \
                   " GROUP BY awesome.aha ORDER BY something OFFSET 10 LIMIT 3"
        self.assertEqual(actual, expected)
        args2 = self.complex_arguments.copy()
        args2['enable_group'] = False
        proc = kojihub.QueryProcessor(**args2)
        actual = " ".join([token for token in str(proc).split() if token])
        expected = "SELECT something FROM awesome JOIN morestuff" \
                   " ORDER BY something OFFSET 10 LIMIT 3"
        self.assertEqual(actual, expected)


    @mock.patch('kojihub.context')
    def test_simple_with_execution(self, context):
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor
        proc = kojihub.QueryProcessor(**self.simple_arguments)
        proc.execute()
        cursor.execute.assert_called_once_with('\nSELECT something\n  FROM awesome\n\n\n \n \n\n \n', {})

    @mock.patch('kojihub.context')
    def test_simple_count_with_execution(self, context):
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor
        cursor.fetchall.return_value = [('some count',)]
        args = self.simple_arguments.copy()
        args['opts'] = {'countOnly': True}
        proc = kojihub.QueryProcessor(**args)
        results = proc.execute()
        cursor.execute.assert_called_once_with('\nSELECT count(*)\n  FROM awesome\n\n\n \n \n\n \n', {})
        self.assertEqual(results, 'some count')

        cursor.reset_mock()
        args['opts']['group'] = 'id'
        args['enable_group'] = True
        proc = kojihub.QueryProcessor(**args)
        results = proc.execute()
        cursor.execute.assert_called_once_with(
            'SELECT count(*)\nFROM (\nSELECT 1\n'
            '  FROM awesome\n\n\n GROUP BY id\n \n\n \n) numrows', {})
        self.assertEqual(results, 'some count')



    @mock.patch('kojihub.context')
    def test_simple_execution_with_iterate(self, context):
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            ('value number 1',),
            ('value number 2',),
            ('value number 3',),
        ]
        proc = kojihub.QueryProcessor(**self.simple_arguments)
        generator = proc.iterate()
        calls = cursor.execute.mock_calls
        result = next(generator)
        # two calls so far..
        self.assertEqual(result, {'something': 'value number 1'})
        self.assertEqual(len(calls), 2)
        result = next(generator)
        # still two.
        self.assertEqual(result, {'something': 'value number 2'})
        self.assertEqual(len(calls), 2)
        # now three.
        result = next(generator)
        self.assertEqual(result, {'something': 'value number 3'})

