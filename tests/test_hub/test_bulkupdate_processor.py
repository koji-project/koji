import mock
import unittest

from kojihub import db


class TestUpdateProcessor(unittest.TestCase):

    maxDiff = None

    def setUp(self):
        self.context = mock.patch('kojihub.db.context').start()
        pass

    def tearDown(self):
        mock.patch.stopall()

    def test_basic_instantiation(self):
        proc = db.BulkUpdateProcessor('sometable')
        repr(proc)
        # No exception!

    def test_basic_bulk_update(self):
        data = [{'id': n, 'field': f'value {n}'} for n in range(2)]
        proc = db.BulkUpdateProcessor('sometable', data=data, match_keys=('id',))

        # check sql
        actual = str(proc)
        expected_sql = ('UPDATE sometable SET field = __kojibulk_sometable.field\n'
                    'FROM (VALUES (%(val_field_0)s, %(val_id_0)s), (%(val_field_1)s, %(val_id_1)s))\n'
                    'AS __kojibulk_sometable (field, id)\n'
                    'WHERE (sometable.id = __kojibulk_sometable.id)')
        self.assertEqual(actual, expected_sql)

        # check values
        expected_values = {'val_field_0': 'value 0',
                    'val_field_1': 'value 1',
                    'val_id_0': 0,
                    'val_id_1': 1}
        self.assertEqual(proc._values, expected_values)

        # verify execution
        cursor = mock.MagicMock()
        self.context.cnx.cursor.return_value = cursor
        proc.execute()
        cursor.execute.assert_called_once_with(
            expected_sql,
            expected_values,
            log_errors=True,
        )

    def test_incomplete(self):
        proc = db.BulkUpdateProcessor('sometable')
        expected = '-- incomplete bulk update'
        self.assertEqual(str(proc), expected)

        with self.assertRaises(ValueError) as ex:
            proc.get_keys()
        expected = 'no update data'
        self.assertEqual(str(ex.exception), expected)

    def test_bad_key(self):
        data = [{'id': n, 100: f'value {n}'} for n in range(2)]
        proc = db.BulkUpdateProcessor('sometable', data=data, match_keys=('id',))
        with self.assertRaises(TypeError) as ex:
            str(proc)
        expected = 'update data must use string keys'
        self.assertEqual(str(ex.exception), expected)

    def test_key_mismatch(self):
        # extra key in later row
        data = [
            {'id': 1, 'A': 1},
            {'id': 2, 'A': 1, 'B': 2},
        ]
        proc = db.BulkUpdateProcessor('sometable', data=data, match_keys=('id',))
        with self.assertRaises(ValueError) as ex:
            str(proc)
        expected = 'mismatched update keys'
        self.assertEqual(str(ex.exception), expected)

        # missing key in later row
        data = [
            {'id': 1, 'A': 1},
            {'id': 2},
        ]
        proc = db.BulkUpdateProcessor('sometable', data=data, match_keys=('id',))
        with self.assertRaises(ValueError) as ex:
            str(proc)
        expected = 'mismatched update keys'
        self.assertEqual(str(ex.exception), expected)
