from unittest import mock
import unittest
import koji
import kojihub

QP = kojihub.QueryProcessor
IP = kojihub.InsertProcessor
UP = kojihub.UpdateProcessor


class TestGroupReqlist(unittest.TestCase):
    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.singleValue = self.query_singleValue
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

    def setUp(self):
        self.maxDiff = None
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context_db = mock.patch('kojihub.db.context').start()
        self.get_tag_id = mock.patch('kojihub.kojihub.get_tag_id').start()
        self.get_group_id = mock.patch('kojihub.kojihub.get_group_id').start()
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
        self.group_req = 'group_req'
        self.taginfo = {'name': self.tag, 'id': 1}
        self.groupinfo = {'name': self.group, 'id': 2}
        self.reqinfo = {'name': self.group_req, 'id': 3}
        self.context_db.event_id = 42
        self.context_db.session.user_id = 24

    def tearDown(self):
        mock.patch.stopall()

    def test_grp_req_add_not_previous(self):
        self.lookup_tag.return_value = self.taginfo
        self.lookup_group.side_effect = [self.groupinfo, self.reqinfo]
        self.get_tag_groups.return_value = {
            2: {'blocked': False, 'display_name': 'group-1', 'group_id': 2, 'tag_id': 1,
                'packagelist': {},
                'grouplist': {}}}

        kojihub.grp_req_add(self.tag, self.group, self.group_req, block=True)

        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'group_req_listing')
        self.assertEqual(update.clauses,
                         ['group_id=%(group_id)s', 'tag_id=%(tag_id)s', 'req_id=%(req_id)s',
                          'active = TRUE'])
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 24})
        self.assertEqual(update.rawdata, {'active': 'NULL'})
        # insert new group
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        values = {
            'blocked': True,
            'create_event': 42,
            'creator_id': 24,
            'group_id': self.groupinfo['id'],
            'req_id': self.reqinfo['id'],
            'tag_id': self.taginfo['id'],
            'type': 'mandatory'
        }
        self.assertEqual(insert.table, 'group_req_listing')
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})

        self.lookup_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_has_calls([
            mock.call(self.group, create=False, strict=True),
            mock.call(self.group_req, create=False, strict=True),
        ])
        self.get_tag_groups.assert_called_once_with(
            self.taginfo['id'], inherit=True, incl_pkgs=False, incl_reqs=True)

    def test_grp_req_add_previous(self):
        self.lookup_tag.return_value = self.taginfo
        self.lookup_group.side_effect = [self.groupinfo, self.reqinfo]
        self.get_tag_groups.return_value = {
            2: {'blocked': False, 'display_name': 'group-1', 'group_id': 2, 'tag_id': 1,
                'packagelist': {},
                'grouplist': {3: {'blocked': False, 'group_id': 2, 'is_metapkg': False,
                                  'req_id': 3, 'tag_id': 1, 'type': 'mandatory'}}}}

        kojihub.grp_req_add(self.tag, self.group, self.group_req, block=True, is_metapkg=True)

        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'group_req_listing')
        self.assertEqual(update.clauses,
                         ['group_id=%(group_id)s', 'tag_id=%(tag_id)s', 'req_id=%(req_id)s',
                          'active = TRUE'])
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 24})
        self.assertEqual(update.rawdata, {'active': 'NULL'})
        # insert new group
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        values = {
            'blocked': True,
            'create_event': 42,
            'creator_id': 24,
            'group_id': self.groupinfo['id'],
            'is_metapkg': True,
            'req_id': self.reqinfo['id'],
            'tag_id': self.taginfo['id'],
            'type': 'mandatory'
        }
        self.assertEqual(insert.table, 'group_req_listing')
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})

        self.lookup_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_has_calls([
            mock.call(self.group, create=False, strict=True),
            mock.call(self.group_req, create=False, strict=True),
        ])
        self.get_tag_groups.assert_called_once_with(
            self.taginfo['id'], inherit=True, incl_pkgs=False, incl_reqs=True)

    def test_grp_req_add_previous_not_changed(self):
        self.lookup_tag.return_value = self.taginfo
        self.lookup_group.side_effect = [self.groupinfo, self.reqinfo]
        self.get_tag_groups.return_value = {
            2: {'blocked': False, 'display_name': 'group-1', 'group_id': 2, 'tag_id': 1,
                'packagelist': {},
                'grouplist': {3: {'blocked': False, 'group_id': 2, 'is_metapkg': False,
                                  'req_id': 3, 'tag_id': 1, 'type': 'mandatory'}}}}

        kojihub.grp_req_add(self.tag, self.group, self.group_req, block=False, is_metapkg=False)

        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.inserts), 0)

        self.lookup_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_has_calls([
            mock.call(self.group, create=False, strict=True),
            mock.call(self.group_req, create=False, strict=True),
        ])
        self.get_tag_groups.assert_called_once_with(
            self.taginfo['id'], inherit=True, incl_pkgs=False, incl_reqs=True)

    def test_grp_req_add_previous_blocked(self):
        self.lookup_tag.return_value = self.taginfo
        self.lookup_group.side_effect = [self.groupinfo, self.reqinfo]
        self.get_tag_groups.return_value = {
            2: {'blocked': False, 'display_name': 'group-1', 'group_id': 2, 'tag_id': 1,
                'packagelist': {},
                'grouplist': {3: {'blocked': True}}}}
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.grp_req_add(self.tag, self.group, self.group_req)
        self.assertEqual(f"requirement on group {self.group_req} blocked in group {self.group}, "
                         f"tag {self.tag}", str(ex.exception))

        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.inserts), 0)

        self.lookup_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_has_calls([
            mock.call(self.group, create=False, strict=True),
            mock.call(self.group_req, create=False, strict=True),
        ])
        self.get_tag_groups.assert_called_once_with(
            self.taginfo['id'], inherit=True, incl_pkgs=False, incl_reqs=True)

    def test_grp_req_add_not_group_in_tag(self):
        self.lookup_tag.return_value = self.taginfo
        self.lookup_group.side_effect = [self.groupinfo, self.reqinfo]
        self.get_tag_groups.return_value = {
            111: {'blocked': False, 'display_name': 'group-1', 'group_id': 111, 'tag_id': 1,
                  'packagelist': {},
                  'grouplist': {8: {'blocked': False, 'group_id': 111, 'is_metapkg': False,
                                    'req_id': 8, 'tag_id': 1, 'type': 'mandatory'}}}}
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.grp_req_add(self.tag, self.group, self.group_req)
        self.assertEqual(f"group {self.group} not present in tag {self.tag}", str(ex.exception))

        self.lookup_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_has_calls([
            mock.call(self.group, create=False, strict=True),
            mock.call(self.group_req, create=False, strict=True),
        ])
        self.get_tag_groups.assert_called_once_with(
            self.taginfo['id'], inherit=True, incl_pkgs=False, incl_reqs=True)

    def test_grp_req_add_group_blocked(self):
        self.lookup_tag.return_value = self.taginfo
        self.lookup_group.side_effect = [self.groupinfo, self.reqinfo]
        self.get_tag_groups.return_value = {
            2: {'blocked': True,
                'grouplist': {8: {'blocked': False, 'group_id': 2}}}}
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.grp_req_add(self.tag, self.group, self.group_req)
        self.assertEqual(f"group {self.group} is blocked in tag {self.tag}", str(ex.exception))

        self.lookup_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_has_calls([
            mock.call(self.group, create=False, strict=True),
            mock.call(self.group_req, create=False, strict=True),
        ])
        self.get_tag_groups.assert_called_once_with(
            self.taginfo['id'], inherit=True, incl_pkgs=False, incl_reqs=True)

    def test_grp_req_remove_force(self):
        self.get_tag_id.return_value = self.taginfo['id']
        self.get_group_id.side_effect = [self.groupinfo['id'], self.reqinfo['id']]
        with mock.patch('kojihub.kojihub.logger') as logger:
            kojihub.grp_req_remove(self.taginfo, self.groupinfo, self.reqinfo, force=True)

            self.assertEqual(len(self.updates), 1)
            update = self.updates[0]
            self.assertEqual(update.table, 'group_req_listing')
            self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 24})
            self.assertEqual(update.clauses, ['req_id=%(req_id)s', 'tag_id=%(tag_id)s',
                                              'group_id = %(grp_id)s', 'active = TRUE'])
            self.assertEqual(update.rawdata, {'active': 'NULL'})

            logger.warning.assert_called_once()
            self.get_tag_id.assert_called_once_with(self.taginfo, strict=True)
            self.get_group_id.assert_has_calls([
                mock.call(self.groupinfo, strict=True),
                mock.call(self.reqinfo, strict=True),
            ])

    def test_grp_req_remove_without_force(self):
        self.get_tag_id.return_value = self.taginfo['id']
        self.get_group_id.side_effect = [self.groupinfo['id'], self.reqinfo['id']]
        with mock.patch('kojihub.kojihub.logger') as logger:
            kojihub.grp_req_remove(self.taginfo, self.groupinfo, self.reqinfo)

        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'group_req_listing')
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 24})
        self.assertEqual(update.clauses, ['req_id=%(req_id)s', 'tag_id=%(tag_id)s',
                                          'group_id = %(grp_id)s', 'active = TRUE'])
        self.assertEqual(update.rawdata, {'active': 'NULL'})
        logger.warning.assert_not_called()
        self.get_tag_id.assert_called_once_with(self.taginfo, strict=True)
        self.get_group_id.assert_has_calls([
            mock.call(self.groupinfo, strict=True),
            mock.call(self.reqinfo, strict=True),
        ])

    @mock.patch('kojihub.kojihub.grp_req_add')
    def test_grp_req_block(self, grp_req_add):
        grp_req_add.return_value = None
        rv = kojihub.grp_req_block(self.taginfo, self.groupinfo, self.reqinfo)
        self.assertEqual(rv, None)
        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.inserts), 0)
        grp_req_add.assert_called_once_with(self.taginfo, self.groupinfo, self.reqinfo, block=True)

    def test_grp_req_unblock_not_blocked_groups(self):
        self.query_singleValue.return_value = None
        self.get_tag_id.return_value = self.taginfo['id']
        self.get_group_id.side_effect = [self.groupinfo['id'], self.reqinfo['id']]
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.grp_req_unblock(self.taginfo, self.groupinfo, self.reqinfo)
        self.assertEqual(f"group req {self.reqinfo['id']} is NOT blocked in group "
                         f"{self.groupinfo['id']}, tag {self.taginfo['id']}", str(ex.exception))

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['group_req_listing'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses,
                         ['active = TRUE', 'group_id=%(grp_id)s', 'req_id = %(req_id)s',
                          'tag_id=%(tag_id)s'])
        self.assertEqual(len(self.updates), 0)

        self.get_tag_id.assert_called_once_with(self.taginfo, strict=True)
        self.get_group_id.assert_has_calls([
            mock.call(self.groupinfo, strict=True),
            mock.call(self.reqinfo, strict=True),
        ])

    def test_grp_req_unblock_valid(self):
        self.query_singleValue.return_value = 123
        self.get_tag_id.return_value = self.taginfo['id']
        self.get_group_id.side_effect = [self.groupinfo['id'], self.reqinfo['id']]
        kojihub.grp_req_unblock(self.taginfo, self.groupinfo, self.reqinfo)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['group_req_listing'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses,
                         ['active = TRUE', 'group_id=%(grp_id)s', 'req_id = %(req_id)s',
                          'tag_id=%(tag_id)s'])
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'group_req_listing')
        self.assertEqual(update.clauses, ['group_id=%(grp_id)s', 'tag_id=%(tag_id)s',
                                          'req_id = %(req_id)s', 'active = TRUE'])
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 24})
        self.assertEqual(update.rawdata, {'active': 'NULL'})

        self.get_tag_id.assert_called_once_with(self.taginfo, strict=True)
        self.get_group_id.assert_has_calls([
            mock.call(self.groupinfo, strict=True),
            mock.call(self.reqinfo, strict=True),
        ])
