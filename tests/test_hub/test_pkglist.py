import mock
import unittest

import koji
import kojihub

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
            raise koji.GenericError(user_id)
    return get_user

class TestPkglistBlock(unittest.TestCase):
    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.user_id = 112233
        self.context.session.user_data = {'name': 'username'}
        self.run_callbacks = mock.patch('koji.plugin.run_callbacks').start()

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('kojihub.readPackageList')
    @mock.patch('kojihub.lookup_package')
    @mock.patch('kojihub.get_tag')
    @mock.patch('kojihub.pkglist_add')
    def test_pkglist_block(self, pkglist_add, get_tag, lookup_package, readPackageList):
        force = mock.MagicMock()
        get_tag.return_value = {'name': 'tag', 'id': 123}
        lookup_package.return_value = {'name': 'pkg', 'id': 321}
        readPackageList.return_value = ['pkg']

        kojihub.pkglist_block('tag', 'pkg', force=force)

        get_tag.assert_called_once_with('tag', strict=True)
        lookup_package.assert_called_once_with('pkg', strict=True)
        pkglist_add.assert_called_once_with('tag', 'pkg', block=True, force=force)

    @mock.patch('kojihub._pkglist_remove')
    @mock.patch('kojihub._pkglist_add')
    @mock.patch('kojihub.readPackageList')
    @mock.patch('kojihub.assert_policy')
    @mock.patch('kojihub.get_tag')
    @mock.patch('kojihub.lookup_package')
    def test_pkglist_unblock(self, lookup_package, get_tag, assert_policy,
            readPackageList, _pkglist_add, _pkglist_remove):
        tag = {'id': 1, 'name': 'tag'}
        pkg = {'id': 2, 'name': 'package', 'owner_id': 3}
        get_tag.return_value = tag
        lookup_package.return_value = pkg
        readPackageList.return_value = {pkg['id']: {
            'blocked': True,
            'tag_id': tag['id'],
            'owner_id': pkg['owner_id'],
            'extra_arches': ''}}

        kojihub.pkglist_unblock('tag', 'pkg', force=False)

        get_tag.assert_called_once_with('tag', strict=True)
        lookup_package.assert_called_once_with('pkg', strict=True)
        assert_policy.assert_called_once_with('package_list', {'tag': tag['id'],
            'action': 'unblock', 'package': pkg['id'], 'force': False}, force=False)
        self.assertEqual(readPackageList.call_count, 2)
        readPackageList.assert_has_calls([
            mock.call(tag['id'], pkgID=pkg['id'], inherit=True),
            mock.call(tag['id'], pkgID=pkg['id'], inherit=True),
        ])
        _pkglist_add.assert_called_once_with(tag['id'], pkg['id'], pkg['owner_id'], False, '')
        _pkglist_remove.assert_called_once_with(tag['id'], pkg['id'])
        self.assertEqual(self.run_callbacks.call_count, 2)
        self.run_callbacks.assert_has_calls([
            mock.call('prePackageListChange', action='unblock', tag=tag, package=pkg, user=None),
            mock.call('postPackageListChange', action='unblock', tag=tag, package=pkg, user=None),
        ])

    @mock.patch('kojihub._pkglist_remove')
    @mock.patch('kojihub._pkglist_add')
    @mock.patch('kojihub.readPackageList')
    @mock.patch('kojihub.assert_policy')
    @mock.patch('kojihub.get_tag')
    @mock.patch('kojihub.lookup_package')
    def test_pkglist_unblock_inherited(self, lookup_package, get_tag, assert_policy,
            readPackageList, _pkglist_add, _pkglist_remove):
        tag_id, pkg_id, owner_id = 1, 2, 3
        get_tag.return_value = {'id': tag_id, 'name': 'tag'}
        lookup_package.return_value = {'id': pkg_id, 'name': 'pkg'}
        readPackageList.return_value = {pkg_id: {
            'blocked': True,
            'tag_id': 4,
            'owner_id': owner_id,
            'extra_arches': ''}}

        kojihub.pkglist_unblock('tag', 'pkg', force=False)

        get_tag.assert_called_once_with('tag', strict=True)
        lookup_package.assert_called_once_with('pkg', strict=True)
        assert_policy.assert_called_once_with('package_list', {'tag': tag_id,
            'action': 'unblock', 'package': pkg_id, 'force': False}, force=False)
        readPackageList.assert_called_once_with(tag_id, pkgID=pkg_id, inherit=True)
        _pkglist_add.assert_called_once_with(tag_id, pkg_id, owner_id, False, '')
        _pkglist_remove.assert_not_called()

    @mock.patch('kojihub._pkglist_remove')
    @mock.patch('kojihub._pkglist_add')
    @mock.patch('kojihub.readPackageList')
    @mock.patch('kojihub.assert_policy')
    @mock.patch('kojihub.get_tag')
    @mock.patch('kojihub.lookup_package')
    def test_pkglist_unblock_not_present(self, lookup_package, get_tag, assert_policy,
            readPackageList, _pkglist_add, _pkglist_remove):
        tag_id, pkg_id = 1, 2
        get_tag.return_value = {'id': tag_id, 'name': 'tag'}
        lookup_package.return_value = {'id': pkg_id, 'name': 'pkg'}
        readPackageList.return_value = {}

        with self.assertRaises(koji.GenericError):
            kojihub.pkglist_unblock('tag', 'pkg', force=False)

        get_tag.assert_called_once_with('tag', strict=True)
        lookup_package.assert_called_once_with('pkg', strict=True)
        assert_policy.assert_called_once_with('package_list', {'tag': tag_id,
            'action': 'unblock', 'package': pkg_id, 'force': False}, force=False)
        readPackageList.assert_called_once_with(tag_id, pkgID=pkg_id, inherit=True)
        _pkglist_add.assert_not_called()
        _pkglist_remove.assert_not_called()

    @mock.patch('kojihub._pkglist_remove')
    @mock.patch('kojihub._pkglist_add')
    @mock.patch('kojihub.readPackageList')
    @mock.patch('kojihub.assert_policy')
    @mock.patch('kojihub.get_tag')
    @mock.patch('kojihub.lookup_package')
    def test_pkglist_unblock_not_blocked(self, lookup_package, get_tag, assert_policy,
            readPackageList, _pkglist_add, _pkglist_remove):
        tag_id, pkg_id, owner_id = 1, 2, 3
        get_tag.return_value = {'id': tag_id, 'name': 'tag'}
        lookup_package.return_value = {'id': pkg_id, 'name': 'pkg'}
        readPackageList.return_value = {pkg_id: {
            'blocked': False,
            'tag_id': tag_id,
            'owner_id': owner_id,
            'extra_arches': ''}}


        with self.assertRaises(koji.GenericError):
            kojihub.pkglist_unblock('tag', 'pkg', force=False)

        get_tag.assert_called_once_with('tag', strict=True)
        lookup_package.assert_called_once_with('pkg', strict=True)
        assert_policy.assert_called_once_with('package_list', {'tag': tag_id,
            'action': 'unblock', 'package': pkg_id, 'force': False}, force=False)
        readPackageList.assert_called_once_with(tag_id, pkgID=pkg_id, inherit=True)
        _pkglist_add.assert_not_called()
        _pkglist_remove.assert_not_called()

    @mock.patch('kojihub.pkglist_add')
    def test_pkglist_setowner(self, pkglist_add):
        force = mock.MagicMock()
        kojihub.pkglist_setowner('tag', 'pkg', 'owner', force=force)
        pkglist_add.assert_called_once_with('tag', 'pkg', owner='owner', force=force, update=True)

    @mock.patch('kojihub.pkglist_add')
    def test_pkglist_setarches(self, pkglist_add):
        force = mock.MagicMock()
        kojihub.pkglist_setarches('tag', 'pkg', 'arches', force=force)
        pkglist_add.assert_called_once_with('tag', 'pkg', extra_arches='arches', force=force, update=True)

    @mock.patch('kojihub._direct_pkglist_add')
    def test_pkglist_add(self, _direct_pkglist_add):
        # just transition of params + policy=True
        kojihub.pkglist_add('tag', 'pkg', owner='owner', block='block',
            extra_arches='extra_arches', force='force', update='update')
        _direct_pkglist_add.assert_called_once_with('tag', 'pkg', 'owner',
            'block', 'extra_arches', 'force', 'update', policy=True)

    @mock.patch('kojihub._pkglist_add')
    @mock.patch('kojihub.readPackageList')
    @mock.patch('kojihub.assert_policy')
    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub.get_tag')
    @mock.patch('kojihub.lookup_package')
    def test_direct_pkglist_add(self, lookup_package, get_tag, get_user,
            assert_policy, readPackageList, _pkglist_add):
        block = False
        extra_arches = 'arch123'
        force=False
        update=False
        policy=True
        tag = {'id': 1, 'name': 'tag'}
        pkg = {'id': 2, 'name': 'pkg', 'owner_id': 3}
        users = [
            {'id': 3, 'name': 'user'},
            {'id': 112233, 'name': 'user'},
        ]
        user = users[0]
        get_tag.return_value = tag
        lookup_package.return_value = pkg
        get_user.side_effect = get_user_factory(users)
        readPackageList.return_value = {}


        kojihub._direct_pkglist_add(tag['name'], pkg['name'],
            user['name'], block=block, extra_arches=extra_arches,
            force=force, update=update, policy=policy)

        get_tag.assert_called_once_with(tag['name'], strict=True)
        lookup_package.assert_called_once_with(pkg['name'], strict=False)
        get_user.assert_has_calls([
            mock.call(user['name'], strict=True),
            mock.call(112233),
        ])
        assert_policy.assert_called_once_with('package_list', {'tag': tag['id'],
            'action': 'add', 'package': pkg['name'], 'force': False}, force=False)
        self.assertEqual(self.run_callbacks.call_count, 2)
        self.run_callbacks.assert_has_calls([
            mock.call('prePackageListChange', action='add', tag=tag,
                package=pkg, owner=user['id'], block=block,
                extra_arches=extra_arches, force=force, update=update,
                user=users[1]),
            mock.call('postPackageListChange', action='add', tag=tag,
                package=pkg, owner=user['id'], block=block,
                extra_arches=extra_arches, force=force, update=update,
                user=users[1]),
        ])
        _pkglist_add.assert_called_once_with(tag['id'], pkg['id'],
            user['id'], block, extra_arches)

    @mock.patch('kojihub._pkglist_add')
    @mock.patch('kojihub.readPackageList')
    @mock.patch('kojihub.assert_policy')
    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub.get_tag')
    @mock.patch('kojihub.lookup_package')
    def test_direct_pkglist_add_no_package(self, lookup_package,
            get_tag, get_user, assert_policy, readPackageList, _pkglist_add):
        block = False
        extra_arches = 'arch123'
        force=False
        update=False
        policy=True
        tag = {'id': 1, 'name': 'tag'}
        pkg = {'id': 2, 'name': 'pkg', 'owner_id': 3}
        user = {'id': 3, 'name': 'user'}
        get_tag.return_value = tag
        lookup_package.return_value = None
        get_user.return_value = user
        readPackageList.return_value = {}

        # package needs to be name, not dict
        with self.assertRaises(koji.GenericError):
            kojihub._direct_pkglist_add(tag['name'], pkg,
                user['name'], block=block, extra_arches=extra_arches,
                force=force, update=update, policy=policy)

        lookup_package.assert_called_once_with(pkg, strict=False)
        self.assertEqual(self.run_callbacks.call_count, 0)
        _pkglist_add.assert_not_called()

    @mock.patch('kojihub._pkglist_add')
    @mock.patch('kojihub.readPackageList')
    @mock.patch('kojihub.assert_policy')
    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub.get_tag')
    @mock.patch('kojihub.lookup_package')
    def test_direct_pkglist_add_no_user(self, lookup_package,
            get_tag, get_user, assert_policy, readPackageList, _pkglist_add):
        block = False
        extra_arches = 'arch123'
        force=False
        update=False
        policy=True
        tag = {'id': 1, 'name': 'tag'}
        pkg = {'id': 2, 'name': 'pkg', 'owner_id': 3}
        user = {'id': 3, 'name': 'user'}
        get_tag.return_value = tag
        lookup_package.return_value = None
        get_user.side_effect = koji.GenericError
        readPackageList.return_value = {}

        with self.assertRaises(koji.GenericError):
            kojihub._direct_pkglist_add(tag['name'], pkg,
                user['name'], block=block, extra_arches=extra_arches,
                force=force, update=update, policy=policy)

        lookup_package.assert_called_once_with(pkg, strict=False)
        self.assertEqual(self.run_callbacks.call_count, 0)
        _pkglist_add.assert_not_called()

    @mock.patch('kojihub._pkglist_add')
    @mock.patch('kojihub.readPackageList')
    @mock.patch('kojihub.assert_policy')
    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub.get_tag')
    @mock.patch('kojihub.lookup_package')
    def test_direct_pkglist_add_new_package(self, lookup_package, get_tag, get_user,
            assert_policy, readPackageList, _pkglist_add):
        block = False
        extra_arches = 'arch123'
        force=False
        update=False
        policy=True
        tag = {'id': 1, 'name': 'tag'}
        pkg = {'id': 2, 'name': 'pkg', 'owner_id': 3}
        users = [
            {'id': 3, 'name': 'user'},
            {'id': 112233, 'name': 'user1'},
        ]
        user = users[0]
        get_tag.return_value = tag
        lookup_package.side_effect = [None, pkg]
        get_user.side_effect = get_user_factory(users)
        readPackageList.return_value = {}


        kojihub._direct_pkglist_add(tag['name'], pkg['name'],
            user['name'], block=block, extra_arches=extra_arches,
            force=force, update=update, policy=policy)

        get_tag.assert_called_once_with(tag['name'], strict=True)
        self.assertEqual(lookup_package.call_count, 2)
        lookup_package.has_calls(
            mock.call(pkg['name'], strict=False),
            mock.call(pkg['name'], create=True),
        )
        get_user.assert_has_calls([
            mock.call(user['name'], strict=True),
            mock.call(112233),
        ])
        assert_policy.assert_called_once_with('package_list', {'tag': tag['id'],
            'action': 'add', 'package': pkg['name'], 'force': False}, force=False)
        self.assertEqual(self.run_callbacks.call_count, 2)
        self.run_callbacks.assert_has_calls([
            mock.call('prePackageListChange', action='add', tag=tag,
                package=pkg, owner=user['id'], block=block,
                extra_arches=extra_arches, force=force, update=update,
                user=users[1]),
            mock.call('postPackageListChange', action='add', tag=tag,
                package=pkg, owner=user['id'], block=block,
                extra_arches=extra_arches, force=force, update=update,
                user=users[1]),
        ])
        _pkglist_add.assert_called_once_with(tag['id'], pkg['id'],
            user['id'], block, extra_arches)

    @mock.patch('kojihub._pkglist_add')
    @mock.patch('kojihub.readPackageList')
    @mock.patch('kojihub.assert_policy')
    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub.get_tag')
    @mock.patch('kojihub.lookup_package')
    def test_direct_pkglist_add_blocked_previously(self,
            lookup_package, get_tag, get_user,
            assert_policy, readPackageList, _pkglist_add):
        block = False
        extra_arches = 'arch123'
        force=False
        update=False
        policy=True
        tag = {'id': 1, 'name': 'tag'}
        pkg = {'id': 2, 'name': 'pkg', 'owner_id': 3}
        users = [
            {'id': 3, 'name': 'user',},
            {'id': 112233, 'name': 'user1'},
        ]
        user = users[0]
        get_tag.return_value = tag
        lookup_package.return_value = pkg
        get_user.side_effect = get_user_factory(users)
        readPackageList.return_value = {pkg['id']: {
            'owner_id': pkg['owner_id'],
            'blocked': True,
            'extra_arches': ''}
        }

        with self.assertRaises(koji.GenericError):
            kojihub._direct_pkglist_add(tag['name'], pkg['name'],
                user['name'], block=block, extra_arches=extra_arches,
                force=force, update=update, policy=policy)

        get_tag.assert_called_once_with(tag['name'], strict=True)
        lookup_package.assert_called_once_with(pkg['name'], strict=False)
        get_user.assert_has_calls([
            mock.call(user['name'], strict=True),
            mock.call(112233),
        ])
        assert_policy.assert_called_once_with('package_list', {'tag': tag['id'],
            'action': 'add', 'package': pkg['name'], 'force': False}, force=False)
        self.run_callbacks.assert_called_once_with(
                'prePackageListChange', action='add', tag=tag,
                package=pkg, owner=user['id'], block=block,
                extra_arches=extra_arches, force=force, update=update,
                user=users[1])
        _pkglist_add.assert_not_called()

    @mock.patch('kojihub._pkglist_add')
    @mock.patch('kojihub.readPackageList')
    @mock.patch('kojihub.assert_policy')
    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub.get_tag')
    @mock.patch('kojihub.lookup_package')
    def test_direct_pkglist_add_blocked_previously_force(self,
            lookup_package, get_tag, get_user,
            assert_policy, readPackageList, _pkglist_add):
        block = False
        extra_arches = 'arch123'
        force=True
        update=False
        policy=True
        tag = {'id': 1, 'name': 'tag'}
        pkg = {'id': 2, 'name': 'pkg', 'owner_id': 3}
        users = [
            {'id': 3, 'name': 'user',},
            {'id': 112233, 'name': 'user1'},
        ]
        user = users[0]
        get_tag.return_value = tag
        lookup_package.return_value = pkg
        get_user.side_effect = get_user_factory(users)
        readPackageList.return_value = {pkg['id']: {
            'owner_id': pkg['owner_id'],
            'blocked': True,
            'extra_arches': ''}
        }

        kojihub._direct_pkglist_add(tag['name'], pkg['name'],
            user['name'], block=block, extra_arches=extra_arches,
            force=force, update=update, policy=policy)

        get_tag.assert_called_once_with(tag['name'], strict=True)
        lookup_package.assert_called_once_with(pkg['name'], strict=False)
        get_user.assert_has_calls([
            mock.call(user['name'], strict=True),
            mock.call(112233),
        ])
        # force + admin
        assert_policy.assert_called_once_with('package_list',
            {'tag': 1, 'action': 'add', 'package': 'pkg', 'force': True}, force=True)

        self.assertEqual(self.run_callbacks.call_count, 2)
        self.run_callbacks.assert_has_calls([
            mock.call('prePackageListChange', action='add', tag=tag,
                package=pkg, owner=user['id'], block=block,
                extra_arches=extra_arches, force=force, update=update,
                user=users[1]),
            mock.call('postPackageListChange', action='add', tag=tag,
                package=pkg, owner=user['id'], block=block,
                extra_arches=extra_arches, force=force, update=update,
                user=users[1]),
        ])
        _pkglist_add.assert_called_once_with(tag['id'], pkg['id'],
            user['id'], block, extra_arches)
