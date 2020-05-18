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
        query.executeOne = mock.MagicMock()
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
        self.context = mock.patch('kojihub.context').start()
        self.get_user = mock.patch('kojihub.get_user').start()
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

    def test_new_group(self):
        name = 'test_group'

        # insufficient permissions
        self.context.session.assertPerm.side_effect = koji.ActionNotAllowed
        with self.assertRaises(koji.GenericError):
            kojihub.new_group(name)
        self.context.session.assertPerm.assert_called_with('admin')
        self.context.session.createUser.not_called()

        # user already exists
        self.context.session.assertPerm.side_effect = None
        self.get_user.return_value = {'id': 1, 'name': name}
        with self.assertRaises(koji.GenericError):
            kojihub.new_group(name)
        self.context.session.assertPerm.assert_called_with('admin')
        self.context.session.createUser.not_called()

        # valid
        self.context.session.assertPerm.side_effect = None
        self.get_user.return_value = None
        kojihub.new_group(name)
        self.context.session.assertPerm.assert_called_with('admin')
        self.context.session.createUser.called_with(name, usertype=koji.USERTYPES['GROUP'])

    def test_add_group_member(self):
        group, gid = 'test_group', 1
        user, uid = 'username', 2

        # no permission
        self.context.session.assertPerm.side_effect = koji.ActionNotAllowed
        with self.assertRaises(koji.ActionNotAllowed):
            kojihub.add_group_member(group, user)
        self.context.session.assertPerm.assert_called_with('admin')
        self.assertEqual(len(self.inserts), 0)

        # non-existent user
        def get_user1(username):
            if username == user:
                return None
            else:
                return {'id': gid, 'name': username, 'usertype': koji.USERTYPES['GROUP']}
        self.context.session.assertPerm.side_effect = None
        self.get_user.side_effect = get_user1
        with self.assertRaises(koji.GenericError):
            kojihub.add_group_member(group, user)
        self.assertEqual(len(self.inserts), 0)

        # non-existent group
        def get_user2(username):
            if username == group:
                return None
            else:
                return {'id': uid, 'name': username, 'usertype': koji.USERTYPES['NORMAL']}
        self.context.session.assertPerm.side_effect = None
        self.get_user.side_effect = get_user2
        with self.assertRaises(koji.GenericError):
            kojihub.add_group_member(group, user)
        self.assertEqual(len(self.inserts), 0)

        # user is group
        def get_user3(username):
            if username == group:
                return {'id': gid, 'name': group, 'usertype': koji.USERTYPES['GROUP']}
            elif username == user:
                return {'id': uid, 'name': username, 'usertype': koji.USERTYPES['GROUP']}
        self.context.session.assertPerm.side_effect = None
        self.get_user.side_effect = get_user3
        with self.assertRaises(koji.GenericError):
            kojihub.add_group_member(group, user)
        self.assertEqual(len(self.inserts), 0)

        # group is not a group
        def get_user4(username):
            if username == group:
                return {'id': gid, 'name': group, 'usertype': koji.USERTYPES['NORMAL']}
            elif username == user:
                return {'id': uid, 'name': username, 'usertype': koji.USERTYPES['NORMAL']}
        self.context.session.assertPerm.side_effect = None
        self.get_user.side_effect = get_user4
        with self.assertRaises(koji.GenericError):
            kojihub.add_group_member(group, user)
        self.assertEqual(len(self.inserts), 0)

        # strict (should raise an error if user is already in group)
        def get_user5(username):
            if username == group:
                return {'id': gid, 'name': group, 'usertype': koji.USERTYPES['GROUP']}
            elif username == user:
                return {'id': uid, 'name': username, 'usertype': koji.USERTYPES['NORMAL']}
        self.context.session.assertPerm.side_effect = None
        self.get_user.side_effect = get_user5
        with self.assertRaises(koji.GenericError):
            kojihub.add_group_member(group, user)
        self.assertEqual(len(self.inserts), 0)

        # same, but non-strict (simply returns)
        kojihub.add_group_member(group, user, strict=False)
        self.assertEqual(len(self.inserts), 0)

        # valid insert (only one insert to user_groups)
        qp = mock.MagicMock(name='qp')
        qp.return_value.executeOne.return_value = None
        self.QueryProcessor.side_effect = qp
        kojihub.add_group_member(group, user, strict=False)
        self.assertEqual(len(self.inserts), 1)
        i = self.inserts[0]
        self.assertEqual(i.table, 'user_groups')
        self.assertEqual(i.data['group_id'], gid)
        self.assertEqual(i.data['user_id'], uid)


    @mock.patch('kojihub.get_group_members')
    def test_drop_group_member(self, get_group_members):
        group, gid = 'test_group', 1
        user, uid = 'username', 2

        # no permission
        self.context.session.assertPerm.side_effect = koji.ActionNotAllowed
        with self.assertRaises(koji.ActionNotAllowed):
            kojihub.drop_group_member(group, user)
        self.context.session.assertPerm.assert_called_with('admin')
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

        # non-existent user
        def get_user1(username, strict=True):
            if username == user:
                if strict:
                    raise koji.GenericError
                else:
                    return None
            else:
                return {'id': gid, 'name': username, 'usertype': koji.USERTYPES['GROUP']}
        self.context.session.assertPerm.side_effect = None
        self.get_user.side_effect = get_user1
        with self.assertRaises(koji.GenericError):
            kojihub.drop_group_member(group, user)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

        # non-existent group
        def get_user2(username, strict=True):
            if username == group:
                if strict:
                    raise koji.GenericError
                else:
                    return None
            else:
                return {'id': uid, 'name': username, 'usertype': koji.USERTYPES['NORMAL']}
        self.context.session.assertPerm.side_effect = None
        self.get_user.side_effect = get_user2
        with self.assertRaises(koji.GenericError):
            kojihub.drop_group_member(group, user)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

        # group is not a group
        def get_user3(username, strict=True):
            if username == group:
                return {'id': gid, 'name': group, 'usertype': koji.USERTYPES['NORMAL']}
            elif username == user:
                return {'id': uid, 'name': username, 'usertype': koji.USERTYPES['NORMAL']}
        self.context.session.assertPerm.side_effect = None
        self.get_user.side_effect = get_user3
        with self.assertRaises(koji.GenericError):
            kojihub.drop_group_member(group, user)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

        # user not in group
        def get_user4(username, strict=True):
            if username == group:
                return {'id': gid, 'name': group, 'usertype': koji.USERTYPES['GROUP']}
            elif username == user:
                return {'id': uid, 'name': username, 'usertype': koji.USERTYPES['NORMAL']}
        self.context.session.assertPerm.side_effect = None
        self.get_user.side_effect = get_user4
        get_group_members.return_value = []
        with self.assertRaises(koji.GenericError):
            kojihub.drop_group_member(group, user)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

        # valid drop
        self.get_user.side_effect = get_user4
        get_group_members.return_value = [{'id': uid, 'name': user}]
        kojihub.drop_group_member(group, user)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 1)
        u = self.updates[0]
        self.assertEqual(u.table, 'user_groups')
        self.assertEqual(u.values['user_id'], uid)
        self.assertEqual(u.values['group_id'], gid)


    @mock.patch('kojihub._multiRow')
    def test_get_group_members(self, _multiRow):
        group, gid = 'test_group', 1

        # no permission
        self.context.session.assertPerm.side_effect = koji.ActionNotAllowed
        with self.assertRaises(koji.ActionNotAllowed):
            kojihub.get_group_members(group)
        self.context.session.assertPerm.assert_called_with('admin')
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

        # non-existent group
        self.context.session.assertPerm.side_effect = None
        self.get_user.return_value = None
        with self.assertRaises(koji.GenericError):
            kojihub.get_group_members(group)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

        # group is not a group
        def get_user1(username, strict=True):
            if username == group:
                return {'id': gid, 'name': group, 'usertype': koji.USERTYPES['NORMAL']}
        self.context.session.assertPerm.side_effect = None
        self.get_user.side_effect = get_user1
        with self.assertRaises(koji.GenericError):
            kojihub.get_group_members(group)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

        # valid query
        def get_user2(username, strict=True):
            if username == group:
                return {'id': gid, 'name': group, 'usertype': koji.USERTYPES['GROUP']}
        self.context.session.assertPerm.side_effect = None
        self.get_user.side_effect = get_user2
        kojihub.get_group_members(group)
        self.assertEqual(len(self.queries), 1)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)
        _multiRow.assert_not_called()
