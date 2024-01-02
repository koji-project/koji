import mock
import unittest

import koji
import kojihub

QP = kojihub.QueryProcessor
IP = kojihub.InsertProcessor
UP = kojihub.UpdateProcessor


def get_user_factory(data):
    def get_user(userInfo, strict=False):
        if isinstance(userInfo, int):
            key = 'id'
        else:
            key = 'name'
        for ui in data:
            if ui[key] == userInfo:
                return ui
        if strict:
            user_id = 112233
            raise koji.GenericError(user_id)
    return get_user


class TestPkglist(unittest.TestCase):

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        insert.make_create = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        update.make_revoke = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.user_id = 112233
        self.context.session.user_data = {'name': 'username'}
        self.context_db = mock.patch('kojihub.db.context').start()
        self.context_db.event_id = 42
        self.context_db.session.user_id = 24
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.run_callbacks = mock.patch('koji.plugin.run_callbacks').start()
        self.read_package_list = mock.patch('kojihub.kojihub.readPackageList').start()
        self.lookup_package = mock.patch('kojihub.kojihub.lookup_package').start()
        self._pkglist_add = mock.patch('kojihub.kojihub._pkglist_add').start()
        self._pkglist_owner_add = mock.patch('kojihub.kojihub._pkglist_owner_add').start()
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self._pkglist_remove = mock.patch('kojihub.kojihub._pkglist_remove').start()
        self.assert_policy = mock.patch('kojihub.kojihub.assert_policy').start()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.tag = {'name': 'tag', 'id': 123}
        self.pkg = {'name': 'pkg', 'id': 321, 'owner_id': 3}
        self.users = [
            {'id': 3, 'name': 'user'},
            {'id': 112233, 'name': 'user'},
        ]
        self.arches = 'arches'

    def tearDown(self):
        mock.patch.stopall()

    def test_pkglist_remove(self):
        self.get_tag.return_value = self.tag
        self.lookup_package.return_value = self.pkg
        self.get_user.return_value = self.users[1]
        kojihub.pkglist_remove(self.tag['name'], self.pkg['name'])
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': self.tag['id'], 'action': 'remove', 'package': self.pkg['id'],
                             'force': False},
            force=False)
        self.assertEqual(self.run_callbacks.call_count, 2)
        self.run_callbacks.assert_has_calls([
            mock.call('prePackageListChange', action='remove', tag=self.tag, package=self.pkg,
                      user=self.users[1]),
            mock.call('postPackageListChange', action='remove', tag=self.tag, package=self.pkg,
                      user=self.users[1]),
        ])
        self._pkglist_remove.assert_called_once_with(self.tag['id'], self.pkg['id'])

    @mock.patch('kojihub.kojihub.pkglist_add')
    def test_pkglist_block(self, pkglist_add):
        force = mock.MagicMock()
        self.get_tag.return_value = self.tag
        self.lookup_package.return_value = self.pkg
        self.read_package_list.return_value = [self.pkg['name']]

        kojihub.pkglist_block(self.tag['name'], self.pkg['name'], force=force)

        self.get_tag.assert_called_once_with(self.tag['name'], strict=True)
        self.lookup_package.assert_called_once_with(self.pkg['name'], strict=True)
        pkglist_add.assert_called_once_with(
            self.tag['name'], self.pkg['name'], block=True, force=force)

    @mock.patch('kojihub.kojihub.pkglist_add')
    def test_pkglist_block_package_error(self, pkglist_add):
        force = mock.MagicMock()
        self.get_tag.return_value = self.tag
        self.lookup_package.return_value = self.pkg
        self.read_package_list.return_value = []

        with self.assertRaises(koji.GenericError) as ex:
            kojihub.pkglist_block(self.tag['name'], self.pkg['name'], force=force)
        self.assertEqual(
            f"Package {self.pkg['name']} is not in tag listing for {self.tag['name']}",
            str(ex.exception))

        self.get_tag.assert_called_once_with(self.tag['name'], strict=True)
        self.lookup_package.assert_called_once_with(self.pkg['name'], strict=True)
        pkglist_add.assert_not_called()

    def test_pkglist_unblock(self,):
        self.get_tag.return_value = self.tag
        self.lookup_package.return_value = self.pkg
        self.read_package_list.return_value = {self.pkg['id']: {
            'blocked': True,
            'tag_id': self.tag['id'],
            'owner_id': self.pkg['owner_id'],
            'extra_arches': ''}}
        self.get_user.side_effect = get_user_factory(self.users)

        kojihub.pkglist_unblock(self.tag['name'], self.pkg['name'], force=False)

        self.get_tag.assert_called_once_with('tag', strict=True)
        self.lookup_package.assert_called_once_with('pkg', strict=True)
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': self.tag['id'], 'action': 'unblock', 'package': self.pkg['id'],
                             'force': False},
            force=False)
        self.assertEqual(self.read_package_list.call_count, 2)
        self.read_package_list.assert_has_calls([
            mock.call(self.tag['id'], pkgID=self.pkg['id'], inherit=True),
            mock.call(self.tag['id'], pkgID=self.pkg['id'], inherit=True),
        ])
        self._pkglist_add.assert_called_once_with(
            self.tag['id'], self.pkg['id'], self.pkg['owner_id'], False, '')
        self._pkglist_remove.assert_called_once_with(self.tag['id'], self.pkg['id'])
        self.assertEqual(self.run_callbacks.call_count, 2)
        self.run_callbacks.assert_has_calls([
            mock.call('prePackageListChange', action='unblock', tag=self.tag, package=self.pkg,
                      user=self.users[1]),
            mock.call('postPackageListChange', action='unblock', tag=self.tag, package=self.pkg,
                      user=self.users[1]),
        ])

    def test_pkglist_unblock_inherited(self):
        self.get_tag.return_value = self.tag
        self.lookup_package.return_value = self.pkg
        self.read_package_list.return_value = {self.pkg['id']: {
            'blocked': True,
            'tag_id': 4,
            'owner_id': self.pkg['owner_id'],
            'extra_arches': ''}}

        kojihub.pkglist_unblock(self.tag['name'], self.pkg['name'], force=False)

        self.get_tag.assert_called_once_with('tag', strict=True)
        self.lookup_package.assert_called_once_with('pkg', strict=True)
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': self.tag['id'], 'action': 'unblock', 'package': self.pkg['id'],
                             'force': False},
            force=False)
        self.read_package_list.assert_called_once_with(
            self.tag['id'], pkgID=self.pkg['id'], inherit=True)
        self._pkglist_add.assert_called_once_with(
            self.tag['id'], self.pkg['id'], self.pkg['owner_id'], False, '')
        self._pkglist_remove.assert_not_called()

    def test_pkglist_unblock_not_present(self):
        self.get_tag.return_value = self.tag
        self.lookup_package.return_value = self.pkg
        self.read_package_list.return_value = {}

        with self.assertRaises(koji.GenericError):
            kojihub.pkglist_unblock(self.tag['name'], self.pkg['name'], force=False)

        self.get_tag.assert_called_once_with(self.tag['name'], strict=True)
        self.lookup_package.assert_called_once_with('pkg', strict=True)
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': self.tag['id'], 'action': 'unblock', 'package': self.pkg['id'],
                             'force': False},
            force=False)
        self.read_package_list.assert_called_once_with(
            self.tag['id'], pkgID=self.pkg['id'], inherit=True)
        self._pkglist_add.assert_not_called()
        self._pkglist_remove.assert_not_called()

    def test_pkglist_unblock_not_blocked(self):
        self.get_tag.return_value = self.tag
        self.lookup_package.return_value = self.pkg
        self.read_package_list.return_value = {self.pkg['id']: {
            'blocked': False,
            'tag_id': self.tag['id'],
            'owner_id': self.pkg['owner_id'],
            'extra_arches': ''}}

        with self.assertRaises(koji.GenericError):
            kojihub.pkglist_unblock(self.tag['name'], self.pkg['name'], force=False)

        self.get_tag.assert_called_once_with(self.tag['name'], strict=True)
        self.lookup_package.assert_called_once_with(self.pkg['name'], strict=True)
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': self.tag['id'], 'action': 'unblock', 'package': self.pkg['id'],
                             'force': False},
            force=False)
        self.read_package_list.assert_called_once_with(
            self.tag['id'], pkgID=self.pkg['id'], inherit=True)
        self._pkglist_add.assert_not_called()
        self._pkglist_remove.assert_not_called()

    @mock.patch('kojihub.kojihub.pkglist_add')
    def test_pkglist_setowner(self, pkglist_add):
        force = mock.MagicMock()
        kojihub.pkglist_setowner(
            self.tag['name'], self.pkg['name'], self.users[0]['name'], force=force)
        pkglist_add.assert_called_once_with(
            self.tag['name'], self.pkg['name'], owner=self.users[0]['name'], force=force,
            update=True)

    @mock.patch('kojihub.kojihub.pkglist_add')
    def test_pkglist_setarches(self, pkglist_add):
        force = mock.MagicMock()
        kojihub.pkglist_setarches(self.tag['name'], self.pkg['name'], self.arches, force=force)
        pkglist_add.assert_called_once_with(self.tag['name'], self.pkg['name'],
                                            extra_arches=self.arches, force=force, update=True)

    @mock.patch('kojihub.kojihub._direct_pkglist_add')
    def test_pkglist_add(self, _direct_pkglist_add):
        # just transition of params + policy=True
        kojihub.pkglist_add(self.tag['name'], self.pkg['name'], owner=self.users[0]['name'],
                            block='block', extra_arches=self.arches, force='force',
                            update='update')
        _direct_pkglist_add.assert_called_once_with(
            self.tag['name'], self.pkg['name'], self.users[0]['name'], 'block', self.arches,
            'force', 'update', policy=True)

    def test_direct_pkglist_add(self):
        block = False
        extra_arches = 'arch123'
        force = False
        update = False
        policy = True
        self.get_tag.return_value = self.tag
        self.lookup_package.return_value = self.pkg
        self.get_user.side_effect = get_user_factory(self.users)
        self.read_package_list.return_value = {}

        kojihub._direct_pkglist_add(self.tag['name'], self.pkg['name'], self.users[0]['name'],
                                    block=block, extra_arches=extra_arches, force=force,
                                    update=update, policy=policy)

        self.get_tag.assert_called_once_with(self.tag['name'], strict=True)
        self.lookup_package.assert_called_once_with(self.pkg['name'], strict=False)
        self.get_user.assert_has_calls([
            mock.call(self.users[0]['name'], strict=True),
            mock.call(self.users[1]['id']),
        ])
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': self.tag['id'], 'action': 'add', 'package': self.pkg['name'],
                             'force': False},
            force=False)
        self.assertEqual(self.run_callbacks.call_count, 2)
        self.run_callbacks.assert_has_calls([
            mock.call('prePackageListChange', action='add', tag=self.tag, package=self.pkg,
                      owner=self.users[0]['id'],
                      block=block, extra_arches=extra_arches, force=force, update=update,
                      user=self.users[1]),
            mock.call('postPackageListChange', action='add', tag=self.tag, package=self.pkg,
                      owner=self.users[0]['id'], block=block, extra_arches=extra_arches,
                      force=force, update=update, user=self.users[1]),
        ])
        self._pkglist_add.assert_called_once_with(
            self.tag['id'], self.pkg['id'], self.users[0]['id'], block, extra_arches)

    def test_direct_pkglist_add_no_package(self):
        block = False
        extra_arches = 'arch123'
        force = False
        update = False
        policy = True
        self.get_tag.return_value = self.tag
        self.lookup_package.return_value = None
        self.get_user.return_value = self.users[0]
        self.read_package_list.return_value = {}

        # package needs to be name, not dict
        with self.assertRaises(koji.GenericError) as ex:
            kojihub._direct_pkglist_add(self.tag['name'], self.pkg['id'], self.users[0]['name'],
                                        block=block, extra_arches=extra_arches, force=force,
                                        update=update, policy=policy)
        self.assertEqual(f"No such package: {self.pkg['id']}", str(ex.exception))

    def test_direct_pkglist_add_not_previous_update_without_force(self):
        self.get_tag.return_value = self.tag
        self.lookup_package.return_value = self.pkg
        self.get_user.return_value = self.users[0]
        self.read_package_list.return_value = {}

        # package needs to be name, not dict
        with self.assertRaises(koji.GenericError) as ex:
            kojihub._direct_pkglist_add(self.tag['name'], self.pkg['name'], self.users[0]['name'],
                                        block=False, extra_arches='arch123', force=False,
                                        update=True, policy=False)
        self.assertEqual(
            f"cannot update: tag {self.tag['name']} has no data for package {self.pkg['name']}",
            str(ex.exception))

        self.get_tag.assert_called_once_with(self.tag['name'], strict=True)
        self.assertEqual(self.lookup_package.call_count, 1)
        self.lookup_package.assert_has_calls([mock.call(self.pkg['name'], strict=False)])
        self.get_user.assert_has_calls([
            mock.call(self.users[0]['name'], strict=True),
            mock.call(self.users[1]['id']),
        ])
        self.assert_policy.assert_not_called()
        self.assertEqual(self.run_callbacks.call_count, 0)
        self.run_callbacks.assert_not_called()
        self._pkglist_add.assert_not_called()

    def test_direct_pkglist_add_pkginfo_dict(self):
        expected = f"Invalid type for id lookup: {self.pkg['name']}"

        self.get_tag.return_value = self.tag
        self.lookup_package.side_effect = koji.GenericError(expected)
        with self.assertRaises(koji.GenericError) as ex:
            kojihub._direct_pkglist_add(self.tag['name'], self.pkg['name'], self.users[0]['name'],
                                        block=False, extra_arches='arch', force=False, update=True)
        self.assertEqual(expected, str(ex.exception))

        self.get_tag.assert_called_once_with(self.tag['name'], strict=True)
        self.assertEqual(self.lookup_package.call_count, 1)
        self.lookup_package.assert_has_calls([mock.call(self.pkg['name'], strict=False)])
        self.get_user.assert_not_called()
        self.assert_policy.assert_not_called()
        self.assertEqual(self.run_callbacks.call_count, 0)
        self.run_callbacks.assert_not_called()
        self._pkglist_add.assert_not_called()

    def test_direct_pkglist_add_no_user(self):
        block = False
        extra_arches = 'arch123'
        force = False
        update = False
        policy = True
        self.get_tag.return_value = self.tag
        self.lookup_package.return_value = None
        self.get_user.side_effect = koji.GenericError
        self.read_package_list.return_value = {}

        with self.assertRaises(koji.GenericError):
            kojihub._direct_pkglist_add(self.tag['name'], self.pkg['name'], self.users[0]['name'],
                                        block=block, extra_arches=extra_arches, force=force,
                                        update=update, policy=policy)

        self.lookup_package.assert_called_once_with(self.pkg['name'], strict=False)
        self.assertEqual(self.run_callbacks.call_count, 0)
        self._pkglist_add.assert_not_called()

    def test_direct_pkglist_add_previous_not_changed(self):
        self.get_tag.return_value = self.tag
        self.lookup_package.side_effect = [None, self.pkg]
        self.get_user.side_effect = get_user_factory(self.users)
        self.read_package_list.return_value = {self.pkg['id']: {
            'owner_id': self.pkg['owner_id'],
            'blocked': False,
            'extra_arches': 'x64_64'}
        }

        kojihub._direct_pkglist_add(self.tag['name'], self.pkg['name'], self.users[0]['name'],
                                    block=False, extra_arches='x64_64', force=False, update=False,
                                    policy=False)

        self.get_tag.assert_called_once_with(self.tag['name'], strict=True)
        self.assertEqual(self.lookup_package.call_count, 2)
        self.lookup_package.assert_has_calls(
            [mock.call(self.pkg['name'], strict=False),
             mock.call(self.pkg['name'], create=True),]
        )
        self.get_user.assert_has_calls([
            mock.call(self.users[0]['name'], strict=True),
            mock.call(self.users[1]['id']),
        ])
        self.assert_policy.assert_not_called()
        self.assertEqual(self.run_callbacks.call_count, 0)
        self.run_callbacks.assert_not_called()
        self._pkglist_add.assert_not_called()
        self._pkglist_owner_add.assert_not_called()

    def test_direct_pkglist_add_not_previous_none_owner_without_force(self):
        self.get_tag.return_value = self.tag
        self.lookup_package.side_effect = [None, self.pkg]
        self.get_user.return_value = self.users[1]
        self.read_package_list.return_value = {}

        with self.assertRaises(koji.GenericError) as ex:
            kojihub._direct_pkglist_add(self.tag['name'], self.pkg['name'], owner=None,
                                        block=False, extra_arches='x64_64', force=False,
                                        update=False,
                                        policy=False)
        self.assertEqual("owner not specified", str(ex.exception))

        self.get_tag.assert_called_once_with(self.tag['name'], strict=True)
        self.assertEqual(self.lookup_package.call_count, 2)
        self.lookup_package.assert_has_calls(
            [mock.call(self.pkg['name'], strict=False),
             mock.call(self.pkg['name'], create=True),]
        )
        self.get_user.assert_called_once_with(self.users[1]['id'])
        self.assert_policy.assert_not_called()
        self.assertEqual(self.run_callbacks.call_count, 0)
        self.run_callbacks.assert_not_called()
        self._pkglist_add.assert_not_called()
        self._pkglist_owner_add.assert_not_called()

    def test_direct_pkglist_add_not_previous_none_owner_with_force_act_block(self):
        block = True
        extra_arches = 'x86_64'
        force = True
        update = False
        policy = False
        self.get_tag.return_value = self.tag
        self.lookup_package.side_effect = [None, self.pkg]
        self.get_user.return_value = self.users[1]
        self.read_package_list.return_value = {}

        kojihub._direct_pkglist_add(self.tag['name'], self.pkg['name'], owner=None,
                                    block=block, extra_arches=extra_arches, force=force,
                                    update=update,
                                    policy=policy)

        self.get_tag.assert_called_once_with(self.tag['name'], strict=True)
        self.assertEqual(self.lookup_package.call_count, 2)
        self.lookup_package.assert_has_calls(
            [mock.call(self.pkg['name'], strict=False),
             mock.call(self.pkg['name'], create=True),]
        )
        self.get_user.assert_called_once_with(self.users[1]['id'])
        self.assert_policy.assert_not_called()
        self.assertEqual(self.run_callbacks.call_count, 2)
        self.run_callbacks.assert_has_calls([
            mock.call('prePackageListChange', action='block', tag=self.tag, package=self.pkg,
                      owner=self.users[1]['id'], block=block, extra_arches=extra_arches,
                      force=force, update=update, user=self.users[1]),
            mock.call('postPackageListChange', action='block', tag=self.tag, package=self.pkg,
                      owner=self.users[1]['id'], block=block, extra_arches=extra_arches,
                      force=force, update=update, user=self.users[1]),
        ])
        self._pkglist_add.assert_called_once_with(
            self.tag['id'], self.pkg['id'], self.users[1]['id'], block, extra_arches)
        self._pkglist_owner_add.assert_not_called()

    def test_direct_pkglist_add_previous_owner_block_extra_arches_none(self):
        block = None
        extra_arches = None
        force = False
        update = True
        policy = False
        self.get_tag.return_value = self.tag
        self.lookup_package.side_effect = [None, self.pkg]
        self.get_user.return_value = self.users[1]
        self.read_package_list.return_value = {self.pkg['id']: {
            'owner_id': self.pkg['owner_id'],
            'blocked': False,
            'extra_arches': 'x64_64'}
        }

        kojihub._direct_pkglist_add(self.tag['name'], self.pkg['name'], owner=None, block=block,
                                    extra_arches=extra_arches, force=force, update=update,
                                    policy=policy)

        self.get_tag.assert_called_once_with(self.tag['name'], strict=True)
        self.assertEqual(self.lookup_package.call_count, 2)
        self.lookup_package.assert_has_calls(
            [mock.call(self.pkg['name'], strict=False),
             mock.call(self.pkg['name'], create=True)],
        )
        self.get_user.assert_called_once_with(self.users[1]['id'])
        self.assert_policy.assert_not_called()
        self.assertEqual(self.run_callbacks.call_count, 0)
        self.run_callbacks.assert_not_called()
        self._pkglist_add.assert_not_called()
        self._pkglist_owner_add.assert_not_called()

    def test_direct_pkglist_add_previous_change_owner_only(self):
        block = False
        extra_arches = 'x64_64'
        force = False
        update = True
        policy = False
        pkg = {'id': 2, 'name': 'pkg', 'owner_id': 2}
        self.get_tag.return_value = self.tag
        self.lookup_package.side_effect = [None, pkg]
        self.get_user.side_effect = get_user_factory(self.users)
        self.read_package_list.return_value = {pkg['id']: {
            'owner_id': pkg['owner_id'],
            'blocked': False,
            'extra_arches': 'x64_64'}
        }

        kojihub._direct_pkglist_add(self.tag['name'], pkg['name'], owner=self.users[0]['name'],
                                    block=block, extra_arches=extra_arches, force=force,
                                    update=update, policy=policy)

        self.get_tag.assert_called_once_with(self.tag['name'], strict=True)
        self.assertEqual(self.lookup_package.call_count, 2)
        self.lookup_package.assert_has_calls(
            [mock.call(pkg['name'], strict=False),
             mock.call(pkg['name'], create=True),]
        )
        self.get_user.assert_has_calls([
            mock.call(self.users[0]['name'], strict=True),
            mock.call(self.users[1]['id']),
        ])
        self.assert_policy.assert_not_called()
        self.assertEqual(self.run_callbacks.call_count, 2)
        self.run_callbacks.assert_has_calls([
            mock.call('prePackageListChange', action='update', tag=self.tag, package=pkg,
                      owner=self.users[0]['id'], block=block, extra_arches=extra_arches,
                      force=force, update=update, user=self.users[1]),
            mock.call('postPackageListChange', action='update', tag=self.tag, package=pkg,
                      owner=self.users[0]['id'], block=block, extra_arches=extra_arches,
                      force=force, update=update, user=self.users[1]),
        ])
        self._pkglist_add.assert_not_called()
        self._pkglist_owner_add.assert_called_once_with(self.tag['id'], pkg['id'], 3)

    def test_direct_pkglist_add_new_package(self):
        block = False
        extra_arches = 'arch123'
        force = False
        update = False
        policy = True
        self.get_tag.return_value = self.tag
        self.lookup_package.side_effect = [None, self.pkg]
        self.get_user.side_effect = get_user_factory(self.users)
        self.read_package_list.return_value = {}

        kojihub._direct_pkglist_add(self.tag['name'], self.pkg['name'], self.users[0]['name'],
                                    block=block, extra_arches=extra_arches, force=force,
                                    update=update, policy=policy)

        self.get_tag.assert_called_once_with(self.tag['name'], strict=True)
        self.assertEqual(self.lookup_package.call_count, 2)
        self.lookup_package.assert_has_calls(
            [mock.call(self.pkg['name'], strict=False),
             mock.call(self.pkg['name'], create=True),]
        )
        self.get_user.assert_has_calls([
            mock.call(self.users[0]['name'], strict=True),
            mock.call(self.users[1]['id']),
        ])
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': self.tag['id'], 'action': 'add', 'package': self.pkg['name'],
                             'force': False},
            force=False)
        self.assertEqual(self.run_callbacks.call_count, 2)
        self.run_callbacks.assert_has_calls([
            mock.call('prePackageListChange', action='add', tag=self.tag, package=self.pkg,
                      owner=self.users[0]['id'], block=block, extra_arches=extra_arches,
                      force=force, update=update, user=self.users[1]),
            mock.call('postPackageListChange', action='add', tag=self.tag, package=self.pkg,
                      owner=self.users[0]['id'], block=block, extra_arches=extra_arches,
                      force=force, update=update, user=self.users[1]),
        ])
        self._pkglist_add.assert_called_once_with(
            self.tag['id'], self.pkg['id'], self.users[0]['id'], block, extra_arches)

    def test_direct_pkglist_add_blocked_previously(self):
        block = False
        extra_arches = 'arch123'
        force = False
        update = False
        policy = True
        self.get_tag.return_value = self.tag
        self.lookup_package.return_value = self.pkg
        self.get_user.side_effect = get_user_factory(self.users)
        self.read_package_list.return_value = {self.pkg['id']: {
            'owner_id': self.pkg['owner_id'],
            'blocked': True,
            'extra_arches': ''}
        }

        with self.assertRaises(koji.GenericError) as ex:
            kojihub._direct_pkglist_add(self.tag['name'], self.pkg['name'], self.users[0]['name'],
                                        block=block, extra_arches=extra_arches, force=force,
                                        update=update, policy=policy)
        self.assertEqual(f"package {self.pkg['name']} is blocked in tag {self.tag['name']}",
                         str(ex.exception))
        self.get_tag.assert_called_once_with(self.tag['name'], strict=True)
        self.lookup_package.assert_called_once_with(self.pkg['name'], strict=False)
        self.get_user.assert_has_calls([
            mock.call(self.users[0]['name'], strict=True),
            mock.call(self.users[1]['id']),
        ])
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': self.tag['id'], 'action': 'add', 'package': self.pkg['name'],
                             'force': False},
            force=False)
        self.run_callbacks.assert_not_called()
        self._pkglist_add.assert_not_called()

    def test_direct_pkglist_add_blocked_previously_force(self):
        block = False
        extra_arches = 'arch123'
        force = True
        update = False
        policy = True
        self.get_tag.return_value = self.tag
        self.lookup_package.return_value = self.pkg
        self.get_user.side_effect = get_user_factory(self.users)
        self.read_package_list.return_value = {self.pkg['id']: {
            'owner_id': self.pkg['owner_id'],
            'blocked': True,
            'extra_arches': ''}
        }

        kojihub._direct_pkglist_add(self.tag['name'], self.pkg['name'], self.users[0]['name'],
                                    block=block, extra_arches=extra_arches, force=force,
                                    update=update, policy=policy)

        self.get_tag.assert_called_once_with(self.tag['name'], strict=True)
        self.lookup_package.assert_called_once_with(self.pkg['name'], strict=False)
        self.get_user.assert_has_calls([
            mock.call(self.users[0]['name'], strict=True),
            mock.call(self.users[1]['id']),
        ])
        # force + admin
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': self.tag['id'], 'action': 'add', 'package': 'pkg',
                             'force': True},
            force=True)

        self.assertEqual(self.run_callbacks.call_count, 2)
        self.run_callbacks.assert_has_calls([
            mock.call('prePackageListChange', action='add', tag=self.tag, package=self.pkg,
                      owner=self.users[0]['id'], block=block, extra_arches=extra_arches,
                      force=force, update=update, user=self.users[1]),
            mock.call('postPackageListChange', action='add', tag=self.tag, package=self.pkg,
                      owner=self.users[0]['id'], block=block, extra_arches=extra_arches,
                      force=force, update=update, user=self.users[1]),
        ])
        self._pkglist_add.assert_called_once_with(
            self.tag['id'], self.pkg['id'], self.users[0]['id'], block, extra_arches)

    def test_pkglist_remove_processor(self):
        kojihub._pkglist_remove(self.tag['id'], self.pkg['id'])

        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'tag_packages')
        self.assertEqual(update.clauses, ['package_id=%(pkg_id)i', 'tag_id=%(tag_id)i'])
        self.assertEqual(update.data, {})
        self.assertEqual(update.rawdata, {})

    def test_pkglist_owner_remove_processor(self):
        kojihub._pkglist_owner_remove(self.tag['id'], self.pkg['id'])

        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'tag_package_owners')
        self.assertEqual(update.clauses, ['package_id=%(pkg_id)i', 'tag_id=%(tag_id)i'])
        self.assertEqual(update.data, {})
        self.assertEqual(update.rawdata, {})

    @mock.patch('kojihub.kojihub._pkglist_owner_remove')
    def test_pkglist_owner_add_processor(self, pkglist_owner_remove):
        pkglist_owner_remove.return_value = None
        kojihub._pkglist_owner_add(self.tag['id'], self.pkg['id'], self.users[0]['name'])

        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        values = {
            'owner': self.users[0]['name'],
            'package_id': self.pkg['id'],
            'tag_id': self.tag['id']
        }
        self.assertEqual(insert.table, 'tag_package_owners')
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})

    @mock.patch('kojihub.kojihub._pkglist_remove')
    def test_pkglist_add_processor(self, pkglist_remove):
        pkglist_remove.return_value = None
        block = False
        extra_arches = 'test-arch'
        kojihub._pkglist_add(
            self.tag['id'], self.pkg['id'], self.users[0]['name'], block, extra_arches)

        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        values = {
            'blocked': block,
            'extra_arches': 'test-arch',
            'package_id': self.pkg['id'],
            'tag_id': self.tag['id']
        }
        self.assertEqual(insert.table, 'tag_packages')
        self.assertEqual(insert.data, values)
        self.assertEqual(insert.rawdata, {})
