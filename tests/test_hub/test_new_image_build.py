import mock

import kojihub
import kojihub.kojihub
from .utils import DBQueryTestCase

IP = kojihub.InsertProcessor


class TestNewImageBuild(DBQueryTestCase):
    def setUp(self):
        super(TestNewImageBuild, self).setUp()
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.insert_execute = mock.MagicMock()
        self.new_typed_build = mock.patch('kojihub.kojihub.new_typed_build').start()
        self.build_info = {
            'id': 100,
            'name': 'test_name',
            'version': 'test_version',
            'release': 'test_release',
            'epoch': 'test_epoch',
            'owner': 'test_owner',
            'extra': {'extra_key': 'extra_value'},
        }

    def tearDown(self):
        mock.patch.stopall()

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = self.insert_execute
        self.inserts.append(insert)
        return insert

    def test_valid_new_image(self):
        self.qp_execute_one_return_value = None
        kojihub.new_image_build(self.build_info)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['image_builds'])
        self.assertEqual(query.columns, ['build_id'])
        self.assertEqual(query.clauses, ['build_id = %(build_id)i'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.values, {'build_id': self.build_info['id']})
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'image_builds')
        self.assertEqual(insert.data, {'build_id': self.build_info['id']})
        self.assertEqual(insert.rawdata, {})
        self.new_typed_build.assert_called_once_with(self.build_info, 'image')

    def test_valid_existing_image(self):
        self.qp_execute_one_return_value = {'build_id': 123}
        kojihub.new_image_build(self.build_info)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['image_builds'])
        self.assertEqual(query.columns, ['build_id'])
        self.assertEqual(query.clauses, ['build_id = %(build_id)i'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.values, {'build_id': self.build_info['id']})
        self.assertEqual(len(self.inserts), 0)
        self.new_typed_build.assert_not_called()
