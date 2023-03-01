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
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.query_executeOne = mock.MagicMock()
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self._dml = mock.patch('kojihub.kojihub._dml').start()
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.get_tag_id = mock.patch('kojihub.kojihub.get_tag_id').start()
        self.check_tag_access = mock.patch('kojihub.kojihub.check_tag_access').start()
        self.writeInheritanceData = mock.patch('kojihub.kojihub.writeInheritanceData').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context_db = mock.patch('kojihub.db.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context_db.session.assertLogin = mock.MagicMock()
        self.buildinfo = {
            'id': 1,
            'name': 'name',
            'version': 'version',
            'release': 'release',
            'state': koji.BUILD_STATES['COMPLETE'],
        }
        self.taginfo = {
            'id': 777,
            'name': 'tag',
        }
        self.userinfo = {
            'id': 999,
            'name': 'user',
        }
        self.event_id = 42

    def tearDown(self):
        mock.patch.stopall()

    def test_simple_tag(self):
        self.check_tag_access.return_value = (True, False, "")
        self.get_build.return_value = self.buildinfo
        self.get_tag.return_value = self.taginfo
        self.get_user.return_value = self.userinfo
        self.context_db.event_id = self.event_id
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
            'build_id': self.buildinfo['id'],
            'create_event': self.event_id,
            'creator_id': self.userinfo['id'],
            'tag_id': self.taginfo['id']
        }
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})
        insert = self.inserts[0]

    def test_simple_tag_with_user(self):
        self.check_tag_access.return_value = (True, False, "")
        self.get_build.return_value = self.buildinfo
        self.get_tag.return_value = self.taginfo
        self.get_user.return_value = self.userinfo
        self.context_db.event_id = self.event_id
        # set return for the already tagged check
        self.query_executeOne.return_value = None

        # call it
        kojihub._tag_build('sometag', 'name-version-release', user_id=self.userinfo['id'])

        self.get_tag.called_once_with('sometag', strict=True)
        self.get_user.called_one_with(self.userinfo['id'], strict=True)
        self.get_build.called_once_with('name-version-release', strict=True)
        self.context.session.assertPerm.assert_not_called()

        # check the insert
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'tag_listing')
        values = {
            'build_id': self.buildinfo['id'],
            'create_event': self.event_id,
            'creator_id': self.userinfo['id'],
            'tag_id': self.taginfo['id']
        }
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})
        insert = self.inserts[0]

    def test_simple_untag(self):
        self.check_tag_access.return_value = (True, False, "")
        self.get_build.return_value = self.buildinfo
        self.get_tag.return_value = self.taginfo
        self.get_user.return_value = self.userinfo
        self.context_db.event_id = self.event_id
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
            'build_id': self.buildinfo['id'],
            'tag_id': self.taginfo['id']
        }
        data = {
            'revoke_event': 42,
            'revoker_id': 999,
        }
        self.assertEqual(update.rawdata, {'active': 'NULL'})
        self.assertEqual(update.data, data)
        self.assertEqual(update.values, values)
        update = self.updates[0]

    def test_simple_untag_with_user(self):
        self.check_tag_access.return_value = (True, False, "")
        self.get_build.return_value = self.buildinfo
        self.get_tag.return_value = self.taginfo
        self.get_user.return_value = self.userinfo
        self.context_db.event_id = self.event_id
        # set return for the already tagged check
        self.query_executeOne.return_value = None

        # call it
        kojihub._untag_build('sometag', 'name-version-release', user_id=self.userinfo['id'])

        self.get_tag.called_once_with('sometag', strict=True)
        self.get_user.called_one_with(self.userinfo['id'], strict=True)
        self.get_build.called_once_with('name-version-release', strict=True)
        self.context.session.assertPerm.assert_not_called()
        self.assertEqual(len(self.inserts), 0)

        # check the update
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'tag_listing')
        values = {
            'build_id': self.buildinfo['id'],
            'tag_id': self.taginfo['id']
        }
        data = {
            'revoke_event': 42,
            'revoker_id': 999,
        }
        self.assertEqual(update.rawdata, {'active': 'NULL'})
        self.assertEqual(update.data, data)
        self.assertEqual(update.values, values)
        update = self.updates[0]


class TestGetTag(unittest.TestCase):

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = self.query_executeOne
        query.iterate = mock.MagicMock()
        self.queries.append(query)
        return query

    def setUp(self):
        self.query_executeOne = mock.MagicMock()
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.tagname = 'test-tag'

    def test_get_tag_invalid_taginfo(self):
        taginfo = {'test-tag': 'value'}
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.get_tag(taginfo, strict=True)
        self.assertEqual(f"Invalid name or id value: {taginfo}", str(ex.exception))

    def test_get_tag_non_exist_tag(self):
        self.query_executeOne.return_value = None
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.get_tag(self.tagname, strict=True)
        self.assertEqual(f"No such tagInfo: '{self.tagname}'", str(ex.exception))

    def test_get_tag_wrong_event(self):
        event = 'unsupported-event'
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.get_tag(self.tagname, event=event)
        self.assertEqual(f"Invalid event: '{event}'", str(ex.exception))
