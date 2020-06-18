import mock
import unittest

import kojihub


class TestUpdateProcessor(unittest.TestCase):

    def test_basic_instantiation(self):
        kojihub.UpdateProcessor('sometable')  # No exception!

    def test_to_string_with_data(self):
        proc = kojihub.UpdateProcessor('sometable', data={'foo': 'bar'})
        actual = str(proc)
        expected = 'UPDATE sometable SET foo = %(data.foo)s'
        self.assertEquals(actual, expected)

    def test_to_values_from_data(self):
        proc = kojihub.UpdateProcessor('sometable', data={'foo': 'bar'})
        actual = proc.get_values()
        expected = {'data.foo': 'bar'}
        self.assertEquals(actual, expected)

    @mock.patch('kojihub.context')
    def test_simple_execution_with_iterate(self, context):
        cursor = mock.MagicMock()
        context.cnx.cursor.return_value = cursor
        proc = kojihub.UpdateProcessor('sometable', data={'foo': 'bar'})
        proc.execute()
        cursor.execute.assert_called_once_with(
            'UPDATE sometable SET foo = %(data.foo)s',
            {'data.foo': 'bar'},
        )
