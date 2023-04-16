import mock

import koji
import kojihub
import kojihub.kojihub
from .utils import DBQueryTestCase

DP = kojihub.DeleteProcessor


class TestRemoveVolume(DBQueryTestCase):
    def setUp(self):
        super(TestRemoveVolume, self).setUp()
        self.DeleteProcessor = mock.patch('kojihub.kojihub.DeleteProcessor',
                                          side_effect=self.getDelete).start()
        self.deletes = []
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def getDelete(self, *args, **kwargs):
        delete = DP(*args, **kwargs)
        delete.execute = mock.MagicMock()
        self.deletes.append(delete)
        return delete

    def test_with_references(self):
        volume_name = 'test-volume'
        volume_dict = {'id': 0, 'name': volume_name}
        self.lookup_name.return_value = volume_dict
        self.qp_execute_return_value = [{'id': 1}]
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.remove_volume(volume_name)
        self.assertEqual(f'volume {volume_name} has build references', str(cm.exception))

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['build'])
        self.assertEqual(query.columns, ['id'])
        self.assertEqual(query.clauses, ['volume_id=%(id)i'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.values, volume_dict)

        self.assertEqual(len(self.deletes), 0)

    def test_valid(self):
        volume_name = 'test-volume'
        volume_dict = {'id': 0, 'name': volume_name}
        self.lookup_name.return_value = volume_dict
        self.qp_execute_return_value = None
        kojihub.remove_volume(volume_name)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['build'])
        self.assertEqual(query.columns, ['id'])
        self.assertEqual(query.clauses, ['volume_id=%(id)i'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.values, volume_dict)

        self.assertEqual(len(self.deletes), 1)
        delete = self.deletes[0]
        self.assertEqual(delete.table, 'volume')
        self.assertEqual(delete.clauses, ['id=%(id)i'])
        self.assertEqual(delete.values, volume_dict)
