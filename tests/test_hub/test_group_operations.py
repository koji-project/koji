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
        query.singleValue = self.query_singleValue
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
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context_db = mock.patch('kojihub.db.context').start()
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.lookup_tag = mock.patch('kojihub.kojihub.lookup_tag').start()
        self.lookup_group = mock.patch('kojihub.kojihub.lookup_group').start()
        self.get_tag_groups = mock.patch('kojihub.kojihub.get_tag_groups').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context_db.session.assertLogin = mock.MagicMock()

        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_singleValue = mock.MagicMock()
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.tag = 'tag'
        self.group = 'group'
        self.taginfo = {'name': self.tag, 'id': 1}
        self.groupinfo = {'name': self.group, 'id': 2}

    def tearDown(self):
        mock.patch.stopall()

    def test_grplist_add_valid(self):
        self.get_tag.return_value = self.taginfo
        self.lookup_group.return_value = self.groupinfo
        self.get_tag_groups.return_value = {}
        self.context_db.event_id = 42
        self.context_db.session.user_id = 24

        kojihub.grplist_add(self.tag, self.group)

        # what was called
        self.context.session.assertPerm.assert_called_once_with('tag')
        self.get_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_called_once_with(self.group, create=True)
        self.get_tag_groups.assert_called_with(self.taginfo['id'], inherit=True, incl_pkgs=False,
                                               incl_reqs=False)
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
            'tag_id': self.taginfo['id'],
            'group_id': self.groupinfo['id'],
            'blocked': False,
        }
        self.assertEqual(insert.table, 'group_config')
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})

    def test_grplist_add_previous_blocked(self):
        self.get_tag.return_value = self.taginfo
        self.lookup_group.return_value = self.groupinfo
        self.get_tag_groups.return_value = {2: {'blocked': True}}

        with self.assertRaises(koji.GenericError) as ex:
            kojihub.grplist_add(self.tag, self.group)
        self.assertEqual(f"group {self.group} is blocked in tag {self.tag}", str(ex.exception))

        # what was called
        self.context.session.assertPerm.assert_called_once_with('tag')
        self.get_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_called_once_with(self.group, create=True)
        self.get_tag_groups.assert_called_with(self.taginfo['id'], inherit=True, incl_pkgs=False,
                                               incl_reqs=False)
        # db
        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.inserts), 0)

    def test_grplist_add_previous_not_changed(self):
        self.get_tag.return_value = self.taginfo
        self.lookup_group.return_value = self.groupinfo
        self.get_tag_groups.return_value = {2: {'exported': 'exp', 'uservisible': True,
                                                'description': 'desc', 'langonly': False,
                                                'biarchonly': False, 'blocked': False,
                                                'display_name': 'test-group', 'is_default': True}}

        kojihub.grplist_add(self.tag, self.group)

        # what was called
        self.context.session.assertPerm.assert_called_once_with('tag')
        self.get_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_called_once_with(self.group, create=True)
        self.get_tag_groups.assert_called_with(self.taginfo['id'], inherit=True, incl_pkgs=False,
                                               incl_reqs=False)
        # db
        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.inserts), 0)

    def test_grplist_add_previous_all_changed(self):
        self.get_tag.return_value = self.taginfo
        self.lookup_group.return_value = self.groupinfo
        self.get_tag_groups.return_value = {2: {'exported': False, 'uservisible': True,
                                                'description': 'desc', 'langonly': False,
                                                'biarchonly': False, 'blocked': False,
                                                'display_name': 'test-group', 'is_default': True}}
        self.context_db.event_id = 42
        self.context_db.session.user_id = 24

        kojihub.grplist_add(self.tag, self.group, block=True, description='test-desc',
                            exported=True, uservisible=False, langonly=True, biarchonly=True,
                            display_name='test-group-new', is_default=False)

        # what was called
        self.context.session.assertPerm.assert_called_once_with('tag')
        self.get_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_called_once_with(self.group, create=True)
        self.get_tag_groups.assert_called_with(self.taginfo['id'], inherit=True, incl_pkgs=False,
                                               incl_reqs=False)
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
            'display_name': 'test-group-new',
            'biarchonly': True,
            'exported': True,
            'uservisible': False,
            'create_event': 42,
            'creator_id': 24,
            'tag_id': self.taginfo['id'],
            'group_id': self.groupinfo['id'],
            'blocked': True,
            'description': 'test-desc',
            'langonly': True,
            'is_default': False,
        }
        self.assertEqual(insert.table, 'group_config')
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})

    def test_grplist_add_previous_few_changed(self):
        self.get_tag.return_value = self.taginfo
        self.lookup_group.return_value = self.groupinfo
        self.get_tag_groups.return_value = {2: {'exported': False, 'uservisible': True,
                                                'description': 'desc', 'langonly': False,
                                                'biarchonly': False, 'blocked': False,
                                                'display_name': 'test-group', 'is_default': True}}
        self.context_db.event_id = 42
        self.context_db.session.user_id = 24

        kojihub.grplist_add(self.tag, self.group, block=True, description='test-desc',
                            exported=True)

        # what was called
        self.context.session.assertPerm.assert_called_once_with('tag')
        self.get_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_called_once_with(self.group, create=True)
        self.get_tag_groups.assert_called_with(self.taginfo['id'], inherit=True, incl_pkgs=False,
                                               incl_reqs=False)
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
            'display_name': 'test-group',
            'biarchonly': False,
            'exported': True,
            'uservisible': True,
            'create_event': 42,
            'creator_id': 24,
            'tag_id': self.taginfo['id'],
            'group_id': self.groupinfo['id'],
            'blocked': True,
            'description': 'test-desc',
            'langonly': False,
            'is_default': True,
        }
        self.assertEqual(insert.table, 'group_config')
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})

    def test_grplist_add_no_admin(self):
        self.context.session.assertPerm.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.grplist_add(self.tag, self.group)
        self.context.session.assertPerm.assert_called_once_with(self.tag)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    def test_grplist_add_no_tag(self):
        self.get_tag.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.grplist_add(self.tag, self.group)
        self.context.session.assertPerm.assert_called_once_with(self.tag)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    def test_grplist_block(self):
        # identical with test_grplist_add except blocked=True
        self.get_tag.return_value = self.taginfo
        self.lookup_group.return_value = self.groupinfo
        self.get_tag_groups.return_value = {}
        self.context_db.event_id = 42
        self.context_db.session.user_id = 24

        kojihub.grplist_block(self.tag, self.group)

        # what was called
        self.context.session.assertPerm.assert_called_once_with('tag')
        self.get_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_called_once_with(self.group, create=True)
        self.get_tag_groups.assert_called_with(self.taginfo['id'], inherit=True, incl_pkgs=False,
                                               incl_reqs=False)
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
            'tag_id': self.taginfo['id'],
            'group_id': self.groupinfo['id'],
            'blocked': True,
        }
        self.assertEqual(insert.table, 'group_config')
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})

    def test_grplist_remove(self):
        self.get_tag.return_value = self.taginfo
        self.lookup_group.return_value = self.groupinfo
        self.context_db.event_id = 42
        self.context_db.session.user_id = 24

        kojihub.grplist_remove(self.tag, self.group)

        # what was called
        self.context.session.assertPerm.assert_called_once_with(self.tag)
        self.get_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_called_once_with(self.group, strict=True)

        # db
        self.assertEqual(len(self.queries), 1)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['group_config'])
        self.assertEqual(query.clauses, ['(active = TRUE)', 'group_id=%(grp_id)s',
                                         'tag_id=%(tag_id)s'])
        self.assertEqual(query.columns, ['active', 'group_id', 'tag_id'])
        update = self.updates[0]
        self.assertEqual(update.table, 'group_config')
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 24})
        self.assertEqual(update.rawdata, {'active': 'NULL'})

        # no group for tag found
        self.reset_db_processors()
        with mock.patch('kojihub.kojihub.QueryProcessor', side_effect=self.getEmptyQuery):
            with self.assertRaises(koji.GenericError) as cm:
                kojihub.grplist_remove(self.tag, self.group)

        self.assertEqual(len(self.queries), 1)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)
        self.assertEqual(cm.exception.args[0], 'No group: group found for tag: tag')

        # force = True
        self.reset_db_processors()
        with mock.patch('kojihub.kojihub.QueryProcessor', side_effect=self.getEmptyQuery):
            kojihub.grplist_remove(self.tag, self.group, force=True)

        self.assertEqual(len(self.queries), 0)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 1)

    def test_grplist_unblock_without_blocked_groups(self):
        # identical with test_grplist_add except blocked=True
        self.lookup_tag.return_value = self.taginfo
        self.lookup_group.return_value = self.groupinfo
        self.query_singleValue.return_value = None

        # will fail for non-blocked group
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.grplist_unblock(self.tag, self.group)
        self.assertEqual(f"group {self.group} is NOT blocked in tag {self.tag}", str(ex.exception))

        # what was called
        self.context.session.assertPerm.assert_called_once_with('tag')
        self.lookup_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_called_once_with(self.group, strict=True)

        # db
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['group_config'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses,
                         ['active = TRUE', 'group_id=%(grp_id)s', 'tag_id=%(tag_id)s'])
        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.inserts), 0)

    def test_grplist_unblock_with_blocked_groups(self):
        # identical with test_grplist_add except blocked=True
        self.lookup_tag.return_value = self.taginfo
        self.lookup_group.return_value = self.groupinfo
        self.query_singleValue.return_value = 333
        self.context_db.event_id = 42
        self.context_db.session.user_id = 24

        kojihub.grplist_unblock(self.tag, self.group)

        # what was called
        self.context.session.assertPerm.assert_called_once_with('tag')
        self.lookup_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_called_once_with(self.group, strict=True)

        # db
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['group_config'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses,
                         ['active = TRUE', 'group_id=%(grp_id)s', 'tag_id=%(tag_id)s'])
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'group_config')
        self.assertEqual(update.clauses,
                         ['group_id=%(grp_id)s', 'tag_id=%(tag_id)s', 'active = TRUE'])
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 24})
        self.assertEqual(update.rawdata, {'active': 'NULL'})
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

        r = kojihub.readTagGroups(self.tag)
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
        r = kojihub.readTagGroups(self.tag)
        self.assertEqual(r, [])

        # with blocked
        self.get_tag_groups.return_value = {1: group.copy()}
        r = kojihub.readTagGroups(self.tag, incl_blocked=True)
        self.assertEqual(r, [{'name': 'a', 'packagelist': [], 'grouplist': [], 'blocked': True}])
