import mock
import unittest

import koji
import kojihub

IP = kojihub.InsertProcessor

class TestNewBuild(unittest.TestCase):
    def setUp(self):
        self.get_rpm = mock.patch('kojihub.get_rpm').start()
        self.get_external_repo_id = mock.patch('kojihub.get_external_repo_id').start()
        self.nextval = mock.patch('kojihub.nextval').start()
        self.Savepoint = mock.patch('kojihub.Savepoint').start()
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                side_effect=self.getInsert).start()
        self.inserts = []
        self.insert_execute = mock.MagicMock()
        self.lookup_package = mock.patch('kojihub.lookup_package').start()
        self.new_package = mock.patch('kojihub.new_package').start()
        self.get_user = mock.patch('kojihub.get_user').start()
        self.get_build = mock.patch('kojihub.get_build').start()
        self.recycle_build = mock.patch('kojihub.recycle_build').start()
        self.context = mock.patch('kojihub.context').start()
        self._singleValue = mock.patch('kojihub._singleValue').start()

    def tearDown(self):
        mock.patch.stopall()

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = self.insert_execute
        self.inserts.append(insert)
        return insert

    def test_valid(self):
        self.get_build.return_value = None
        self._singleValue.return_value = 65 # free build id
        self.new_package.return_value = 54
        self.get_user.return_value = {'id': 123}
        data = {
            'name': 'test_name',
            'version': 'test_version',
            'release': 'test_release',
            'epoch': 'test_epoch',
            'owner': 'test_owner',
            'extra': {'extra_key': 'extra_value'},
        }

        kojihub.new_build(data)

        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'build')
        self.assertEqual(insert.data, {
            'completion_time': 'NOW',
            'epoch': 'test_epoch',
            'extra': '{"extra_key": "extra_value"}',
            'id': 65,
            'owner': 123,
            'pkg_id': 54,
            'release': 'test_release',
            'source': None,
            'start_time': 'NOW',
            'state': 1,
            'task_id': None,
            'version': 'test_version',
            'volume_id': 0
        })

    def test_empty_data(self):
        with self.assertRaises(koji.GenericError):
            kojihub.new_build({})
        self.assertEqual(len(self.inserts), 0)

    def test_wrong_pkg_id(self):
        self.lookup_package.side_effect = koji.GenericError
        data = {
            'pkg_id': 444,
            'name': 'test_name',
            'version': 'test_version',
            'release': 'test_release',
            'epoch': 'test_epoch',
            'owner': 'test_owner',
            'extra': {'extra_key': 'extra_value'},
        }

        with self.assertRaises(koji.GenericError):
            kojihub.new_build(data)

        self.assertEqual(len(self.inserts), 0)

    def test_missing_pkg_id_name(self):
        data = {
            'version': 'test_version',
            'release': 'test_release',
            'epoch': 'test_epoch',
            'owner': 'test_owner',
            'extra': {'extra_key': 'extra_value'},
        }

        with self.assertRaises(koji.GenericError):
            kojihub.new_build(data)

        self.assertEqual(len(self.inserts), 0)

    def test_wrong_owner(self):
        self.get_user.side_effect = koji.GenericError
        data = {
            'owner': 123456,
            'name': 'test_name',
            'version': 'test_version',
            'release': 'test_release',
            'epoch': 'test_epoch',
            'extra': {'extra_key': 'extra_value'},
        }

        with self.assertRaises(koji.GenericError):
            kojihub.new_build(data)

        self.assertEqual(len(self.inserts), 0)

    def test_missing_vre(self):
        self.get_user.side_effect = koji.GenericError
        data = {
            'name': 'test_name',
            'version': 'test_version',
            'release': 'test_release',
            'epoch': 'test_epoch',
        }

        for item in ('version', 'release', 'epoch'):
            d = data.copy()
            del d[item]
            with self.assertRaises(koji.GenericError):
                kojihub.new_build(d)

        self.assertEqual(len(self.inserts), 0)

    def test_wrong_extra(self):
        # extra dict contains unserializable data
        class CantDoJSON(object):
            pass

        data = {
            'owner': 123456,
            'name': 'test_name',
            'version': 'test_version',
            'release': 'test_release',
            'epoch': 'test_epoch',
            'extra': {'extra_key': CantDoJSON()},
        }

        with self.assertRaises(koji.GenericError):
            kojihub.new_build(data)

        self.assertEqual(len(self.inserts), 0)
