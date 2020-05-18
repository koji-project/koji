import mock
import unittest
import koji
import kojihub

QP = kojihub.QueryProcessor
IP = kojihub.InsertProcessor
UP = kojihub.UpdateProcessor

class TestGrouplist(unittest.TestCase):
    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        self.queries.append(query)
        return query

    def getEmptyQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.execute.return_value = None
        self.queries.append(query)
        return query

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

    def reset_db_processors(self):
        self.queries = []
        self.updates = []
        self.inserts = []

    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        self.get_tag = mock.patch('kojihub.get_tag').start()
        self.lookup_tag = mock.patch('kojihub.lookup_tag').start()
        self.lookup_group = mock.patch('kojihub.lookup_group').start()
        self.get_tag_groups = mock.patch('kojihub.get_tag_groups').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()

        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                side_effect=self.getQuery).start()
        self.queries = []
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.UpdateProcessor',
                side_effect=self.getUpdate).start()
        self.updates = []

    def tearDown(self):
        mock.patch.stopall()

    def test_grplist_add(self):
        tag = 'tag'
        group = 'group'
        self.get_tag.return_value = {'name': 'tag', 'id': 'tag_id'}
        self.lookup_group.return_value = {'name': 'group', 'id': 'group_id'}
        self.get_tag_groups.return_value = {}
        self.context.event_id = 42
        self.context.session.user_id = 24

        kojihub.grplist_add(tag, group)

        # what was called
        self.context.session.assertPerm.assert_called_once_with('tag')
        self.get_tag.assert_called_once_with(tag, strict=True)
        self.lookup_group.assert_called_once_with(group, create=True)
        self.get_tag_groups.assert_called_with('tag_id', inherit=True,
                incl_pkgs=False, incl_reqs=False)
        # db
        # revoke
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'group_config')
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 24})
        self.assertEqual(update.rawdata, {'active': 'NULL'})
        # insert new group
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        values = {
            'display_name': 'group',
            'biarchonly': False,
            'exported': True,
            'uservisible': True,
            'create_event': 42,
            'creator_id': 24,
            'tag_id': 'tag_id',
            'group_id': 'group_id',
            'blocked': False,
        }
        self.assertEqual(insert.table, 'group_config')
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})

    def test_grplist_add_no_admin(self):
        self.context.session.assertPerm.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.grplist_add('tag', 'group')
        self.context.session.assertPerm.assert_called_once_with('tag')
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    def test_grplist_add_no_tag(self):
        self.get_tag.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.grplist_add('tag', 'group')
        self.context.session.assertPerm.assert_called_once_with('tag')
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    def test_grplist_block(self):
        # identical with test_grplist_add except blocked=True
        tag = 'tag'
        group = 'group'
        self.get_tag.return_value = {'name': 'tag', 'id': 'tag_id'}
        self.lookup_group.return_value = {'name': 'group', 'id': 'group_id'}
        self.get_tag_groups.return_value = {}
        self.context.event_id = 42
        self.context.session.user_id = 24

        kojihub.grplist_block(tag, group)

        # what was called
        self.context.session.assertPerm.assert_called_once_with('tag')
        self.get_tag.assert_called_once_with(tag, strict=True)
        self.lookup_group.assert_called_once_with(group, create=True)
        self.get_tag_groups.assert_called_with('tag_id', inherit=True,
                incl_pkgs=False, incl_reqs=False)
        # db
        # revoke
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'group_config')
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 24})
        self.assertEqual(update.rawdata, {'active': 'NULL'})
        # insert new group
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        values = {
            'display_name': 'group',
            'biarchonly': False,
            'exported': True,
            'uservisible': True,
            'create_event': 42,
            'creator_id': 24,
            'tag_id': 'tag_id',
            'group_id': 'group_id',
            'blocked': True,
        }
        self.assertEqual(insert.table, 'group_config')
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})

    def test_grplist_remove(self):
        tag = 'tag'
        group = 'group'
        self.get_tag.return_value = {'name': 'tag', 'id': 'tag_id'}
        self.lookup_group.return_value = {'name': 'group', 'id': 'group_id'}
        self.context.event_id = 42
        self.context.session.user_id = 24

        kojihub.grplist_remove(tag, group)

        # what was called
        self.context.session.assertPerm.assert_called_once_with('tag')
        self.get_tag.assert_called_once_with(tag, strict=True)
        self.lookup_group.assert_called_once_with(group, strict=True)

        # db
        self.assertEqual(len(self.queries), 1)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 1)
        query = self.queries[0]
        self.assertEqual(' '.join(str(query).split()),
                         'SELECT active, group_id, tag_id FROM group_config'
                         ' WHERE ((active = TRUE))'
                         ' AND (group_id=%(grp_id)s)'
                         ' AND (tag_id=%(tag_id)s)')
        update = self.updates[0]
        self.assertEqual(update.table, 'group_config')
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 24})
        self.assertEqual(update.rawdata, {'active': 'NULL'})

        # no group for tag found
        self.reset_db_processors()
        with mock.patch('kojihub.QueryProcessor', side_effect=self.getEmptyQuery):
            with self.assertRaises(koji.GenericError) as cm:
                kojihub.grplist_remove(tag, group)

        self.assertEqual(len(self.queries), 1)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)
        self.assertEqual(cm.exception.args[0],
                         'No group: group found for tag: tag')

        # force = True
        self.reset_db_processors()
        with mock.patch('kojihub.QueryProcessor',
                        side_effect=self.getEmptyQuery):
            kojihub.grplist_remove(tag, group, force=True)

        self.assertEqual(len(self.queries), 0)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 1)

    def test_grplist_unblock(self):
        # identical with test_grplist_add except blocked=True
        tag = 'tag'
        group = 'group'
        self.lookup_tag.return_value = {'name': 'tag', 'id': 'tag_id'}
        self.lookup_group.return_value = {'name': 'group', 'id': 'group_id'}
        #self.context.event_id = 42
        #self.context.session.user_id = 24

        # will fail for non-blocked group
        with self.assertRaises(koji.GenericError):
            kojihub.grplist_unblock(tag, group)

        # what was called
        self.context.session.assertPerm.assert_called_once_with('tag')
        self.lookup_tag.assert_called_once_with(tag, strict=True)
        self.lookup_group.assert_called_once_with(group, strict=True)

        # db
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        q = "SELECT blocked FROM group_config WHERE (active = TRUE) AND (group_id=%(grp_id)s) AND (tag_id=%(tag_id)s) FOR UPDATE"
        actual = ' '.join(str(query).split())
        self.assertEqual(actual, q)
        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.inserts), 0)

    def test_readTagGroups_empty(self):
        self.get_tag_groups.return_value = {}

        r = kojihub.readTagGroups('tag')
        self.assertEqual(r, [])

        self.get_tag_groups.assert_called_once_with('tag', None, True, True, True)

    def test_readTagGroups(self):
        group = {
            'name': 'a',
            'packagelist': {},
            'grouplist': {},
            'blocked': False,
        }
        self.get_tag_groups.return_value = {1: group}

        r = kojihub.readTagGroups('tag')
        self.assertEqual(r, [{'name': 'a', 'packagelist': [], 'grouplist': [], 'blocked': False}])

    def test_readTagGroups_blocked(self):
        group = {
            'name': 'a',
            'packagelist': {},
            'grouplist': {},
            'blocked': True,
        }
        self.get_tag_groups.return_value = {1: group.copy()}

        # without blocked
        r = kojihub.readTagGroups('tag')
        self.assertEqual(r, [])

        # with blocked
        self.get_tag_groups.return_value = {1: group.copy()}
        r = kojihub.readTagGroups('tag', incl_blocked=True)
        self.assertEqual(r, [{'name': 'a', 'packagelist': [], 'grouplist': [], 'blocked': True}])
