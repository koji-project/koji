import mock
import unittest

import koji
import kojihub

QP = kojihub.QueryProcessor
UP = kojihub.UpdateProcessor
IP = kojihub.InsertProcessor


class TestTagBuild(unittest.TestCase):

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = self.query_executeOne
        query.iterate = mock.MagicMock()
        self.queries.append(query)
        return query

    def setUp(self):
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.UpdateProcessor',
                side_effect=self.getUpdate).start()
        self.updates = []
        self.query_executeOne = mock.MagicMock()
        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                side_effect=self.getQuery).start()
        self.queries = []
        self._dml = mock.patch('kojihub._dml').start()
        self.get_tag = mock.patch('kojihub.get_tag').start()
        self.get_build = mock.patch('kojihub.get_build').start()
        self.get_user = mock.patch('kojihub.get_user').start()
        self.get_tag_id = mock.patch('kojihub.get_tag_id').start()
        self.check_tag_access = mock.patch('kojihub.check_tag_access').start()
        self.writeInheritanceData = mock.patch('kojihub.writeInheritanceData').start()
        self.context = mock.patch('kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_simple_tag(self):
        self.check_tag_access.return_value = (True, False, "")
        self.get_build.return_value = {
            'id': 1,
            'name': 'name',
            'version': 'version',
            'release': 'release',
            'state': koji.BUILD_STATES['COMPLETE'],
        }
        self.get_tag.return_value = {
            'id': 777,
            'name': 'tag',
        }
        self.get_user.return_value = {
            'id': 999,
            'name': 'user',
        }
        self.context.event_id = 42
        # set return for the already tagged check
        self.query_executeOne.return_value = None

        # call it
        kojihub._tag_build('sometag', 'name-version-release')

        self.get_tag.called_once_with('sometag', strict=True)
        self.get_build.called_once_with('name-version-release', strict=True)
        self.context.session.assertPerm.called_with('admin')

        # check the insert
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'tag_listing')
        values = {
            'build_id': 1,
            'create_event': 42,
            'creator_id': 999,
            'tag_id': 777
        }
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})
        insert = self.inserts[0]


    def test_simple_untag(self):
        self.check_tag_access.return_value = (True, False, "")
        self.get_build.return_value = {
            'id': 1,
            'name': 'name',
            'version': 'version',
            'release': 'release',
            'state': koji.BUILD_STATES['COMPLETE'],
        }
        self.get_tag.return_value = {
            'id': 777,
            'name': 'tag',
        }
        self.get_user.return_value = {
            'id': 999,
            'name': 'user',
        }
        self.context.event_id = 42
        # set return for the already tagged check
        self.query_executeOne.return_value = None

        # call it
        kojihub._untag_build('sometag', 'name-version-release')

        self.get_tag.called_once_with('sometag', strict=True)
        self.get_build.called_once_with('name-version-release', strict=True)
        self.context.session.assertPerm.called_with('admin')
        self.assertEqual(len(self.inserts), 0)

        # check the update
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'tag_listing')
        values = {
            'build_id': 1,
            'tag_id': 777
        }
        data = {
            'revoke_event': 42,
            'revoker_id': 999,
        }
        self.assertEqual(update.rawdata, {'active': 'NULL'})
        self.assertEqual(update.data, data)
        self.assertEqual(update.values, values)
        update = self.updates[0]
