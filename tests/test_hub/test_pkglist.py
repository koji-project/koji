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
            user_id = 112233
            raise koji.GenericError(user_id)
    return get_user


class TestPkglist(unittest.TestCase):
    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.user_id = 112233
        self.context.session.user_data = {'name': 'username'}
        self.run_callbacks = mock.patch('koji.plugin.run_callbacks').start()
        self.read_package_list = mock.patch('kojihub.readPackageList').start()
        self.lookup_package = mock.patch('kojihub.lookup_package').start()
        self._pkglist_add = mock.patch('kojihub._pkglist_add').start()
        self.get_tag = mock.patch('kojihub.get_tag').start()
        self._pkglist_remove = mock.patch('kojihub._pkglist_remove').start()
        self.assert_policy = mock.patch('kojihub.assert_policy').start()
        self.get_user = mock.patch('kojihub.get_user').start()

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('kojihub.pkglist_add')
    def test_pkglist_block(self, pkglist_add):
        force = mock.MagicMock()
        self.get_tag.return_value = {'name': 'tag', 'id': 123}
        self.lookup_package.return_value = {'name': 'pkg', 'id': 321}
        self.read_package_list.return_value = ['pkg']

        kojihub.pkglist_block('tag', 'pkg', force=force)

        self.get_tag.assert_called_once_with('tag', strict=True)
        self.lookup_package.assert_called_once_with('pkg', strict=True)
        pkglist_add.assert_called_once_with('tag', 'pkg', block=True, force=force)

    @mock.patch('kojihub.pkglist_add')
    def test_pkglist_block_package_error(self, pkglist_add):
        pkg_name = 'pkg'
        tag_name = 'tag'
        force = mock.MagicMock()
        self.get_tag.return_value = {'name': tag_name, 'id': 123}
        self.lookup_package.return_value = {'name': pkg_name, 'id': 321}
        self.read_package_list.return_value = []

        with self.assertRaises(koji.GenericError) as ex:
            kojihub.pkglist_block('tag', 'pkg', force=force)
        self.assertEqual("Package %s is not in tag listing for %s" % (pkg_name, tag_name),
                         str(ex.exception))

        self.get_tag.assert_called_once_with('tag', strict=True)
        self.lookup_package.assert_called_once_with('pkg', strict=True)
        pkglist_add.assert_not_called()

    def test_pkglist_unblock(self,):
        tag = {'id': 1, 'name': 'tag'}
        pkg = {'id': 2, 'name': 'package', 'owner_id': 3}
        self.get_tag.return_value = tag
        self.lookup_package.return_value = pkg
        self.read_package_list.return_value = {pkg['id']: {
            'blocked': True,
            'tag_id': tag['id'],
            'owner_id': pkg['owner_id'],
            'extra_arches': ''}}
        users = [
            {'id': 3, 'name': 'user'},
            {'id': 112233, 'name': 'user'},
        ]
        user = users[1]
        self.get_user.side_effect = get_user_factory(users)

        kojihub.pkglist_unblock('tag', 'pkg', force=False)

        self.get_tag.assert_called_once_with('tag', strict=True)
        self.lookup_package.assert_called_once_with('pkg', strict=True)
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': tag['id'], 'action': 'unblock', 'package': pkg['id'],
                             'force': False},
            force=False)
        self.assertEqual(self.read_package_list.call_count, 2)
        self.read_package_list.assert_has_calls([
            mock.call(tag['id'], pkgID=pkg['id'], inherit=True),
            mock.call(tag['id'], pkgID=pkg['id'], inherit=True),
        ])
        self._pkglist_add.assert_called_once_with(tag['id'], pkg['id'], pkg['owner_id'], False, '')
        self._pkglist_remove.assert_called_once_with(tag['id'], pkg['id'])
        self.assertEqual(self.run_callbacks.call_count, 2)
        self.run_callbacks.assert_has_calls([
            mock.call('prePackageListChange', action='unblock', tag=tag, package=pkg, user=user),
            mock.call('postPackageListChange', action='unblock', tag=tag, package=pkg, user=user),
        ])

    def test_pkglist_unblock_inherited(self):
        tag_id, pkg_id, owner_id = 1, 2, 3
        self.get_tag.return_value = {'id': tag_id, 'name': 'tag'}
        self.lookup_package.return_value = {'id': pkg_id, 'name': 'pkg'}
        self.read_package_list.return_value = {pkg_id: {
            'blocked': True,
            'tag_id': 4,
            'owner_id': owner_id,
            'extra_arches': ''}}

        kojihub.pkglist_unblock('tag', 'pkg', force=False)

        self.get_tag.assert_called_once_with('tag', strict=True)
        self.lookup_package.assert_called_once_with('pkg', strict=True)
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': tag_id, 'action': 'unblock', 'package': pkg_id,
                             'force': False},
            force=False)
        self.read_package_list.assert_called_once_with(tag_id, pkgID=pkg_id, inherit=True)
        self._pkglist_add.assert_called_once_with(tag_id, pkg_id, owner_id, False, '')
        self._pkglist_remove.assert_not_called()

    def test_pkglist_unblock_not_present(self):
        tag_id, pkg_id = 1, 2
        self.get_tag.return_value = {'id': tag_id, 'name': 'tag'}
        self.lookup_package.return_value = {'id': pkg_id, 'name': 'pkg'}
        self.read_package_list.return_value = {}

        with self.assertRaises(koji.GenericError):
            kojihub.pkglist_unblock('tag', 'pkg', force=False)

        self.get_tag.assert_called_once_with('tag', strict=True)
        self.lookup_package.assert_called_once_with('pkg', strict=True)
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': tag_id, 'action': 'unblock', 'package': pkg_id,
                             'force': False},
            force=False)
        self.read_package_list.assert_called_once_with(tag_id, pkgID=pkg_id, inherit=True)
        self._pkglist_add.assert_not_called()
        self._pkglist_remove.assert_not_called()

    def test_pkglist_unblock_not_blocked(self):
        tag_id, pkg_id, owner_id = 1, 2, 3
        self.get_tag.return_value = {'id': tag_id, 'name': 'tag'}
        self.lookup_package.return_value = {'id': pkg_id, 'name': 'pkg'}
        self.read_package_list.return_value = {pkg_id: {
            'blocked': False,
            'tag_id': tag_id,
            'owner_id': owner_id,
            'extra_arches': ''}}

        with self.assertRaises(koji.GenericError):
            kojihub.pkglist_unblock('tag', 'pkg', force=False)

        self.get_tag.assert_called_once_with('tag', strict=True)
        self.lookup_package.assert_called_once_with('pkg', strict=True)
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': tag_id, 'action': 'unblock', 'package': pkg_id,
                             'force': False},
            force=False)
        self.read_package_list.assert_called_once_with(tag_id, pkgID=pkg_id, inherit=True)
        self._pkglist_add.assert_not_called()
        self._pkglist_remove.assert_not_called()

    @mock.patch('kojihub.pkglist_add')
    def test_pkglist_setowner(self, pkglist_add):
        force = mock.MagicMock()
        kojihub.pkglist_setowner('tag', 'pkg', 'owner', force=force)
        pkglist_add.assert_called_once_with('tag', 'pkg', owner='owner', force=force, update=True)

    @mock.patch('kojihub.pkglist_add')
    def test_pkglist_setarches(self, pkglist_add):
        force = mock.MagicMock()
        kojihub.pkglist_setarches('tag', 'pkg', 'arches', force=force)
        pkglist_add.assert_called_once_with('tag', 'pkg', extra_arches='arches', force=force,
                                            update=True)

    @mock.patch('kojihub._direct_pkglist_add')
    def test_pkglist_add(self, _direct_pkglist_add):
        # just transition of params + policy=True
        kojihub.pkglist_add('tag', 'pkg', owner='owner', block='block',
                            extra_arches='extra_arches', force='force', update='update')
        _direct_pkglist_add.assert_called_once_with('tag', 'pkg', 'owner', 'block', 'extra_arches',
                                                    'force', 'update', policy=True)

    def test_direct_pkglist_add(self):
        block = False
        extra_arches = 'arch123'
        force = False
        update = False
        policy = True
        tag = {'id': 1, 'name': 'tag'}
        pkg = {'id': 2, 'name': 'pkg', 'owner_id': 3}
        users = [
            {'id': 3, 'name': 'user'},
            {'id': 112233, 'name': 'user'},
        ]
        user = users[0]
        self.get_tag.return_value = tag
        self.lookup_package.return_value = pkg
        self.get_user.side_effect = get_user_factory(users)
        self.read_package_list.return_value = {}

        kojihub._direct_pkglist_add(tag['name'], pkg['name'], user['name'], block=block,
                                    extra_arches=extra_arches, force=force, update=update,
                                    policy=policy)

        self.get_tag.assert_called_once_with(tag['name'], strict=True)
        self.lookup_package.assert_called_once_with(pkg['name'], strict=False)
        self.get_user.assert_has_calls([
            mock.call(user['name'], strict=True),
            mock.call(112233),
        ])
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': tag['id'], 'action': 'add', 'package': pkg['name'],
                             'force': False},
            force=False)
        self.assertEqual(self.run_callbacks.call_count, 2)
        self.run_callbacks.assert_has_calls([
            mock.call('prePackageListChange', action='add', tag=tag, package=pkg, owner=user['id'],
                      block=block, extra_arches=extra_arches, force=force, update=update,
                      user=users[1]),
            mock.call('postPackageListChange', action='add', tag=tag, package=pkg,
                      owner=user['id'], block=block, extra_arches=extra_arches, force=force,
                      update=update, user=users[1]),
        ])
        self._pkglist_add.assert_called_once_with(
            tag['id'], pkg['id'], user['id'], block, extra_arches)

    def test_direct_pkglist_add_no_package(self):
        block = False
        extra_arches = 'arch123'
        force = False
        update = False
        policy = True
        tag = {'id': 1, 'name': 'tag'}
        pkg = {'id': 2, 'name': 'pkg', 'owner_id': 3}
        user = {'id': 3, 'name': 'user'}
        self.get_tag.return_value = tag
        self.lookup_package.return_value = None
        self.get_user.return_value = user
        self.read_package_list.return_value = {}

        # package needs to be name, not dict
        with self.assertRaises(koji.GenericError) as ex:
            kojihub._direct_pkglist_add(tag['name'], pkg, user['name'], block=block,
                                        extra_arches=extra_arches, force=force, update=update,
                                        policy=policy)
        self.assertEqual("No such package: %s" % pkg, str(ex.exception))

    def test_direct_pkglist_add_pkginfo_dict(self):
        pkg = {'id': 2, 'name': 'pkg', 'owner_id': 3}
        user = 'user'
        tag = {'id': 1, 'name': 'tag'}
        expected = "Invalid type for id lookup: %s" % pkg

        self.get_tag.return_value = tag
        self.lookup_package.side_effect = koji.GenericError(expected)
        with self.assertRaises(koji.GenericError) as ex:
            kojihub._direct_pkglist_add(tag['name'], pkg, user, block=False, extra_arches='arch',
                                        force=False, update=True)
        self.assertEqual(expected, str(ex.exception))

    def test_direct_pkglist_add_no_user(self):
        block = False
        extra_arches = 'arch123'
        force = False
        update = False
        policy = True
        tag = {'id': 1, 'name': 'tag'}
        pkg = {'id': 2, 'name': 'pkg', 'owner_id': 3}
        user = {'id': 3, 'name': 'user'}
        self.get_tag.return_value = tag
        self.lookup_package.return_value = None
        self.get_user.side_effect = koji.GenericError
        self.read_package_list.return_value = {}

        with self.assertRaises(koji.GenericError):
            kojihub._direct_pkglist_add(tag['name'], pkg, user['name'], block=block,
                                        extra_arches=extra_arches, force=force, update=update,
                                        policy=policy)

        self.lookup_package.assert_called_once_with(pkg, strict=False)
        self.assertEqual(self.run_callbacks.call_count, 0)
        self._pkglist_add.assert_not_called()

    def test_direct_pkglist_add_new_package(self):
        block = False
        extra_arches = 'arch123'
        force = False
        update = False
        policy = True
        tag = {'id': 1, 'name': 'tag'}
        pkg = {'id': 2, 'name': 'pkg', 'owner_id': 3}
        users = [
            {'id': 3, 'name': 'user'},
            {'id': 112233, 'name': 'user1'},
        ]
        user = users[0]
        self.get_tag.return_value = tag
        self.lookup_package.side_effect = [None, pkg]
        self.get_user.side_effect = get_user_factory(users)
        self.read_package_list.return_value = {}

        kojihub._direct_pkglist_add(tag['name'], pkg['name'], user['name'], block=block,
                                    extra_arches=extra_arches, force=force, update=update,
                                    policy=policy)

        self.get_tag.assert_called_once_with(tag['name'], strict=True)
        self.assertEqual(self.lookup_package.call_count, 2)
        self.lookup_package.has_calls(
            mock.call(pkg['name'], strict=False),
            mock.call(pkg['name'], create=True),
        )
        self.get_user.assert_has_calls([
            mock.call(user['name'], strict=True),
            mock.call(112233),
        ])
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': tag['id'], 'action': 'add', 'package': pkg['name'],
                             'force': False},
            force=False)
        self.assertEqual(self.run_callbacks.call_count, 2)
        self.run_callbacks.assert_has_calls([
            mock.call('prePackageListChange', action='add', tag=tag, package=pkg, owner=user['id'],
                      block=block, extra_arches=extra_arches, force=force, update=update,
                      user=users[1]),
            mock.call('postPackageListChange', action='add', tag=tag, package=pkg,
                      owner=user['id'], block=block, extra_arches=extra_arches, force=force,
                      update=update, user=users[1]),
        ])
        self._pkglist_add.assert_called_once_with(
            tag['id'], pkg['id'], user['id'], block, extra_arches)

    def test_direct_pkglist_add_blocked_previously(self):
        block = False
        extra_arches = 'arch123'
        force = False
        update = False
        policy = True
        tag = {'id': 1, 'name': 'tag'}
        pkg = {'id': 2, 'name': 'pkg', 'owner_id': 3}
        users = [
            {'id': 3, 'name': 'user', },
            {'id': 112233, 'name': 'user1'},
        ]
        user = users[0]
        self.get_tag.return_value = tag
        self.lookup_package.return_value = pkg
        self.get_user.side_effect = get_user_factory(users)
        self.read_package_list.return_value = {pkg['id']: {
            'owner_id': pkg['owner_id'],
            'blocked': True,
            'extra_arches': ''}
        }

        with self.assertRaises(koji.GenericError):
            kojihub._direct_pkglist_add(tag['name'], pkg['name'], user['name'], block=block,
                                        extra_arches=extra_arches, force=force, update=update,
                                        policy=policy)

        self.get_tag.assert_called_once_with(tag['name'], strict=True)
        self.lookup_package.assert_called_once_with(pkg['name'], strict=False)
        self.get_user.assert_has_calls([
            mock.call(user['name'], strict=True),
            mock.call(112233),
        ])
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': tag['id'], 'action': 'add', 'package': pkg['name'],
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
        tag = {'id': 1, 'name': 'tag'}
        pkg = {'id': 2, 'name': 'pkg', 'owner_id': 3}
        users = [
            {'id': 3, 'name': 'user', },
            {'id': 112233, 'name': 'user1'},
        ]
        user = users[0]
        self.get_tag.return_value = tag
        self.lookup_package.return_value = pkg
        self.get_user.side_effect = get_user_factory(users)
        self.read_package_list.return_value = {pkg['id']: {
            'owner_id': pkg['owner_id'],
            'blocked': True,
            'extra_arches': ''}
        }

        kojihub._direct_pkglist_add(tag['name'], pkg['name'], user['name'], block=block,
                                    extra_arches=extra_arches, force=force, update=update,
                                    policy=policy)

        self.get_tag.assert_called_once_with(tag['name'], strict=True)
        self.lookup_package.assert_called_once_with(pkg['name'], strict=False)
        self.get_user.assert_has_calls([
            mock.call(user['name'], strict=True),
            mock.call(112233),
        ])
        # force + admin
        self.assert_policy.assert_called_once_with(
            'package_list', {'tag': 1, 'action': 'add', 'package': 'pkg', 'force': True},
            force=True)

        self.assertEqual(self.run_callbacks.call_count, 2)
        self.run_callbacks.assert_has_calls([
            mock.call('prePackageListChange', action='add', tag=tag, package=pkg, owner=user['id'],
                      block=block, extra_arches=extra_arches, force=force, update=update,
                      user=users[1]),
            mock.call('postPackageListChange', action='add', tag=tag, package=pkg,
                      owner=user['id'], block=block, extra_arches=extra_arches, force=force,
                      update=update, user=users[1]),
        ])
        self._pkglist_add.assert_called_once_with(
            tag['id'], pkg['id'], user['id'], block, extra_arches)
