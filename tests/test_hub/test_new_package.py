import mock

import koji
import kojihub
import kojihub.kojihub
from .utils import DBQueryTestCase

IP = kojihub.InsertProcessor


class TestNewPackage(DBQueryTestCase):
    def setUp(self):
        super(TestNewPackage, self).setUp()
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.insert_execute = mock.MagicMock()
        self.nextval = mock.patch('kojihub.kojihub.nextval').start()
        self.verify_name_internal = mock.patch('kojihub.kojihub.verify_name_internal').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.pkg_name = 'test-pkg'

    def tearDown(self):
        mock.patch.stopall()

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = self.insert_execute
        self.inserts.append(insert)
        return insert

    def test_pkg_already_exist(self):
        self.verify_name_internal.return_value = None
        self.qp_single_value_return_value = 2
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.new_package(self.pkg_name, strict=True)
        self.assertEqual("Package already exists [id 2]", str(cm.exception))
        self.verify_name_internal.assert_called_once_with(self.pkg_name)
        self.nextval.assert_not_called()

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['package'])
        self.assertEqual(query.columns, ['id'])
        self.assertEqual(query.clauses, ['name=%(name)s'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.values, {'name': self.pkg_name})
        self.assertEqual(len(self.inserts), 0)

    def test_pkg_new(self):
        self.verify_name_internal.return_value = None
        self.qp_single_value_return_value = None
        self.nextval.return_value = 3
        rv = kojihub.new_package(self.pkg_name, strict=True)
        self.assertEqual(rv, 3)
        self.verify_name_internal.assert_called_once_with(self.pkg_name)
        self.nextval.assert_called_once_with('package_id_seq')

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['package'])
        self.assertEqual(query.columns, ['id'])
        self.assertEqual(query.clauses, ['name=%(name)s'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.values, {'name': self.pkg_name})
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'package')
        self.assertEqual(insert.data, {'id': 3, 'name': self.pkg_name})
        self.assertEqual(insert.rawdata, {})
