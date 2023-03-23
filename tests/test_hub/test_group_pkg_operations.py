import mock
import unittest
import koji
import kojihub

QP = kojihub.QueryProcessor
IP = kojihub.InsertProcessor
UP = kojihub.UpdateProcessor


class TestGroupPkglist(unittest.TestCase):
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
        self.pkg = 'test-pkg'
        self.taginfo = {'name': self.tag, 'id': 1}
        self.groupinfo = {'name': self.group, 'id': 2}
        self.pkginfo = {'name': self.pkg, 'id': 3}
        self.context_db.event_id = 42
        self.context_db.session.user_id = 24

    def test_grp_pkg_add_previous_changed(self):
        self.lookup_tag.return_value = self.taginfo
        self.lookup_group.return_value = self.groupinfo
        self.get_tag_groups.return_value = {
            2: {'blocked': False, 'display_name': 'group-1', 'group_id': 2, 'tag_id': 1,
                'packagelist': {'test-pkg': {'basearchonly': None, 'blocked': False,
                                             'group_id': 3, 'requires': None, 'tag_id': 1,
                                             'type': 'mandatory'}},
                'grouplist': {}}}
        kojihub.grp_pkg_add(self.tag, self.group, self.pkg, block=True, type='test-type')

        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'group_package_listing')
        self.assertEqual(update.clauses,
                         ['group_id=%(group_id)s', 'tag_id=%(tag_id)s', 'package=%(package)s',
                          'active = TRUE'])
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 24})
        self.assertEqual(update.rawdata, {'active': 'NULL'})
        # insert new group
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        values = {
            'basearchonly': None,
            'blocked': True,
            'create_event': 42,
            'creator_id': 24,
            'group_id': self.groupinfo['id'],
            'package': self.pkg,
            'requires': None,
            'tag_id': self.taginfo['id'],
            'type': 'test-type'
        }
        self.assertEqual(insert.table, 'group_package_listing')
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})

        self.lookup_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_called_once_with(self.group, strict=True)
        self.get_tag_groups.assert_called_once_with(
            self.taginfo['id'], inherit=True, incl_pkgs=True, incl_reqs=False)

    def test_grp_pkg_add_previous_not_changed(self):
        self.lookup_tag.return_value = self.taginfo
        self.lookup_group.return_value = self.groupinfo
        self.get_tag_groups.return_value = {
            2: {'blocked': False, 'display_name': 'group-1', 'group_id': 2, 'tag_id': 1,
                'packagelist': {'test-pkg': {'basearchonly': None, 'blocked': False,
                                             'group_id': 3, 'requires': None, 'tag_id': 1,
                                             'type': 'mandatory'}},
                'grouplist': {}}}
        kojihub.grp_pkg_add(self.tag, self.group, self.pkg, block=False, type='mandatory')

        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.inserts), 0)

        self.lookup_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_called_once_with(self.group, strict=True)
        self.get_tag_groups.assert_called_once_with(
            self.taginfo['id'], inherit=True, incl_pkgs=True, incl_reqs=False)

    def test_grp_pkg_add_not_previous(self):
        self.lookup_tag.return_value = self.taginfo
        self.lookup_group.return_value = self.groupinfo
        self.get_tag_groups.return_value = {
            2: {'blocked': False, 'display_name': 'group-1', 'group_id': 2, 'tag_id': 1,
                'packagelist': {},
                'grouplist': {}}}
        kojihub.grp_pkg_add(self.tag, self.group, self.pkg)

        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'group_package_listing')
        self.assertEqual(update.clauses,
                         ['group_id=%(group_id)s', 'tag_id=%(tag_id)s', 'package=%(package)s',
                          'active = TRUE'])
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 24})
        self.assertEqual(update.rawdata, {'active': 'NULL'})
        # insert new group
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        values = {
            'blocked': False,
            'create_event': 42,
            'creator_id': 24,
            'group_id': self.groupinfo['id'],
            'package': self.pkg,
            'tag_id': self.taginfo['id'],
            'type': 'mandatory'
        }
        self.assertEqual(insert.table, 'group_package_listing')
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})

        self.lookup_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_called_once_with(self.group, strict=True)
        self.get_tag_groups.assert_called_once_with(
            self.taginfo['id'], inherit=True, incl_pkgs=True, incl_reqs=False)

    def test_grp_pkg_add_previous_blocked(self):
        self.lookup_tag.return_value = self.taginfo
        self.lookup_group.return_value = self.groupinfo
        self.get_tag_groups.return_value = {
            2: {'blocked': False, 'display_name': 'group-1', 'group_id': 2, 'tag_id': 1,
                'packagelist': {'test-pkg': {'basearchonly': None, 'blocked': True, 'group_id': 3,
                                             'requires': None, 'tag_id': 1, 'type': 'mandatory'}},
                'grouplist': {}}}
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.grp_pkg_add(self.tag, self.group, self.pkg)
        self.assertEqual(f"package {self.pkg} blocked in group {self.group}, tag {self.tag}",
                         str(ex.exception))

        self.lookup_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_called_once_with(self.group, strict=True)
        self.get_tag_groups.assert_called_once_with(
            self.taginfo['id'], inherit=True, incl_pkgs=True, incl_reqs=False)

    def test_grp_pkg_add_not_group_in_tag(self):
        self.lookup_tag.return_value = self.taginfo
        self.lookup_group.return_value = self.groupinfo
        self.get_tag_groups.return_value = {
            111: {'blocked': False, 'display_name': 'group-1', 'group_id': 111, 'tag_id': 1,
                  'packagelist': {'pkg': {'basearchonly': None, 'blocked': False, 'group_id': 3,
                                          'requires': None, 'tag_id': 1, 'type': 'mandatory'}},
                  'grouplist': {}}}

        with self.assertRaises(koji.GenericError) as ex:
            kojihub.grp_pkg_add(self.tag, self.group, self.pkg)
        self.assertEqual(f"group {self.group} not present in tag {self.tag}", str(ex.exception))

        self.lookup_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_called_once_with(self.group, strict=True)
        self.get_tag_groups.assert_called_once_with(
            self.taginfo['id'], inherit=True, incl_pkgs=True, incl_reqs=False)

    def test_grp_pkg_add_group_blocked(self):
        self.lookup_tag.return_value = self.taginfo
        self.lookup_group.return_value = self.groupinfo
        self.get_tag_groups.return_value = {
            2: {'blocked': True,
                'packagelist': {self.pkg: {'basearchonly': None, 'blocked': False, 'group_id': 3,
                                           'requires': None, 'tag_id': 1, 'type': 'mandatory'}},
                'grouplist': {}}}
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.grp_pkg_add(self.tag, self.group, self.pkg)
        self.assertEqual(f"group {self.group} is blocked in tag {self.tag}", str(ex.exception))

        self.lookup_tag.assert_called_once_with(self.tag, strict=True)
        self.lookup_group.assert_called_once_with(self.group, strict=True)
        self.get_tag_groups.assert_called_once_with(
            self.taginfo['id'], inherit=True, incl_pkgs=True, incl_reqs=False)

    def test_grp_req_remove(self):
        self.get_tag_id.return_value = self.taginfo['id']
        self.get_group_id.return_value = self.groupinfo['id']
        kojihub.grp_pkg_remove(self.taginfo, self.groupinfo, self.pkg)

        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'group_package_listing')
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 24})
        self.assertEqual(update.clauses, ['package=%(pkg_name)s', 'tag_id=%(tag_id)s',
                                          'group_id = %(grp_id)s', 'active = TRUE'])
        self.assertEqual(update.rawdata, {'active': 'NULL'})
        self.get_tag_id.assert_called_once_with(self.taginfo, strict=True)
        self.get_group_id.assert_called_once_with(self.groupinfo, strict=True)

    @mock.patch('kojihub.kojihub.grp_pkg_add')
    def test_grp_pkg_block(self, grp_pkg_add):
        grp_pkg_add.return_value = None
        rv = kojihub.grp_pkg_block(self.taginfo, self.groupinfo, self.pkg)
        self.assertEqual(rv, None)
        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.inserts), 0)
        grp_pkg_add.assert_called_once_with(self.taginfo, self.groupinfo, self.pkg, block=True)

    def test_grp_pkg_unblock_not_blocked_groups(self):
        self.query_singleValue.return_value = None
        self.get_tag_id.return_value = self.taginfo['id']
        self.get_group_id.return_value = self.groupinfo['id']
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.grp_pkg_unblock(self.taginfo, self.groupinfo, self.pkg)
        self.assertEqual(f"package {self.pkg} is NOT blocked in group {self.groupinfo['id']}, "
                         f"tag {self.taginfo['id']}", str(ex.exception))

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['group_package_listing'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses,
                         ['active = TRUE', 'group_id=%(grp_id)s', 'package = %(pkg_name)s',
                          'tag_id=%(tag_id)s'])
        self.assertEqual(len(self.updates), 0)

        self.get_tag_id.assert_called_once_with(self.taginfo, strict=True)
        self.get_group_id.assert_called_once_with(self.groupinfo, strict=True)

    def test_grp_pkg_unblock_valid(self):
        self.query_singleValue.return_value = 123
        self.get_tag_id.return_value = self.taginfo['id']
        self.get_group_id.return_value = self.groupinfo['id']
        kojihub.grp_pkg_unblock(self.taginfo, self.groupinfo, self.pkg)

        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['group_package_listing'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses,
                         ['active = TRUE', 'group_id=%(grp_id)s', 'package = %(pkg_name)s',
                          'tag_id=%(tag_id)s'])
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'group_package_listing')
        self.assertEqual(update.clauses, ['group_id=%(grp_id)s', 'tag_id=%(tag_id)s',
                                          'package = %(pkg_name)s', 'active = TRUE'])
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 24})
        self.assertEqual(update.rawdata, {'active': 'NULL'})

        self.get_tag_id.assert_called_once_with(self.taginfo, strict=True)
        self.get_group_id.assert_called_once_with(self.groupinfo, strict=True)
