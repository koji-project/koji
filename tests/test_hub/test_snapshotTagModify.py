import mock
import unittest
import koji
import kojihub


class TestSnapshotTagModify(unittest.TestCase):
    def setUp(self):
        self._create_tag = mock.patch('kojihub._create_tag').start()
        self.get_tag = mock.patch('kojihub.get_tag').start()
        self.get_build = mock.patch('kojihub.get_build').start()
        self.get_user = mock.patch('kojihub.get_user').start()
        self._direct_tag_build = mock.patch('kojihub._direct_tag_build').start()
        self._direct_untag_build = mock.patch('kojihub._direct_untag_build').start()
        self._tag_build = mock.patch('kojihub._tag_build').start()
        self._untag_build = mock.patch('kojihub._untag_build').start()
        self._direct_pkglist_add = mock.patch('kojihub._direct_pkglist_add').start()
        self._delete_event_id = mock.patch('kojihub._delete_event_id').start()
        self._grplist_add = mock.patch('kojihub._grplist_add').start()
        self._grplist_remove = mock.patch('kojihub._grplist_remove').start()
        self._grp_pkg_add = mock.patch('kojihub._grp_pkg_add').start()
        self._grp_pkg_remove = mock.patch('kojihub._grp_pkg_remove').start()
        self._grp_req_add = mock.patch('kojihub._grp_req_add').start()
        self._grp_req_remove = mock.patch('kojihub._grp_req_remove').start()
        self.readTagGroups = mock.patch('kojihub.readTagGroups').start()
        self.readTaggedBuilds = mock.patch('kojihub.readTaggedBuilds').start()
        self.context = mock.patch('kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.edit_tag = mock.patch('kojihub.edit_tag').start()
        self.hub = kojihub.RootExports()
        self.hub.listPackages = mock.MagicMock()
        self.hub.massTag = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_no_permission(self):
        self.context.session.assertPerm.side_effect = koji.ActionNotAllowed
        with self.assertRaises(koji.ActionNotAllowed):
            self.hub.snapshotTagModify('src', 'dst')
        self.context.session.assertPerm.assert_called_once_with('tag')

    def test_builds_without_pkgs(self):
        with self.assertRaises(koji.ParameterError):
            self.hub.snapshotTagModify('src', 'dst', builds=True, pkgs=False)

    def test_nonexisting_dst(self):
        self.get_tag.side_effect = [{'id': 1, 'locked': False}, koji.GenericError('xx')]
        with self.assertRaises(koji.GenericError) as cm:
            self.hub.snapshotTagModify('src', 'dst')
        self.assertEqual("xx", str(cm.exception))

    def test_locked_without_force_both(self):
        self.get_tag.side_effect = [{'id': 1, 'locked': True}, {'id': 2, 'locked': True}]
        with self.assertRaises(koji.GenericError) as cm:
            self.hub.snapshotTagModify('src', 'dst')
        self.assertEqual("Source or destination tag is locked, use force to copy", str(cm.exception))

    def test_locked_without_force_src(self):
        self.get_tag.side_effect = [{'id': 1, 'locked': True}, {'id': 2, 'locked': False}]
        with self.assertRaises(koji.GenericError) as cm:
            self.hub.snapshotTagModify('src', 'dst')
        self.assertEqual("Source or destination tag is locked, use force to copy", str(cm.exception))

    def test_locked_without_force_dst(self):
        self.get_tag.side_effect = [{'id': 1, 'locked': False}, {'id': 2, 'locked': True}]
        with self.assertRaises(koji.GenericError) as cm:
            self.hub.snapshotTagModify('src', 'dst')
        self.assertEqual("Source or destination tag is locked, use force to copy", str(cm.exception))

    def test_correct_all(self):
        src = {
            'id': 1,
            'name': 'src',
            'parent': 2,
            'locked': True,
            'arches': 'x86_64 s390x',
            'perm_id': 3,
            'maven_support': True,
            'maven_include_all': False,
            'extra': {'extra_field': 'text'},
        }
        dst = src.copy()
        dst['id'] = 11
        dst['name'] = 'dst'
        pkg1 = {
            'tag_id': src['id'],
            'package_name': 'pkg1',
            'owner_name': 'owner',
            'blocked': False,
            'extra_arches': None,
        }
        pkg2 = {
            'tag_id': dst['id'],
            'package_name': 'pkg2',
            'owner_name': 'owner',
            'blocked': False,
            'extra_arches': None,
        }
        build = {
            'id': 21,
            'nvr': 'n-v-r',
            'package_name': pkg1['package_name'],
            'tag_name': 'src',
        }
        build2 = {
            'id': 22,
            'nvr': 'n-v-r2',
            'package_name': pkg1['package_name'],
            'tag_name': 'dst',
        }
        user = {
            'id': 321,
            'name': 'username',
        }
        src_group1 = {
            'id': 1,
            'name': 'group1',
            'blocked': False,
            'packagelist': [{'package': pkg1['package_name'], 'tag_id': src['id']}],
            'grouplist': [{'group_id': 5, 'name': 'group5', 'blocked': False}],
            'inherited': False,
        }
        src_group2 = {
            'id': 2,
            'name': 'group2',
            'blocked': False,
            'package_list': [],
            'grouplist': [],
            'inherited': False,
        }
        dst_group1 = {
            'id': 3,
            'name': 'group1',
            'blocked': False,
            'packagelist': [{'package': pkg2['package_name'], 'tag_id': dst['id']}],
            'grouplist': [{'group_id': 4, 'name': 'group4', 'blocked': False}],
            'inherited': False,
        }
        self.get_tag.side_effect = [
            src,  # src
            dst,  # dst
            dst,  # edited dst
        ]
        self.get_user.return_value = user
        self._create_tag.return_value = dst['id']
        self.hub.listPackages.side_effect = [[pkg1], [pkg2]]
        self.readTaggedBuilds.side_effect = [[build], [build2]]
        self.readTagGroups.side_effect = [[src_group1, src_group2], [dst_group1]]
        self.context.session.user_id = user['id']

        # call
        self.hub.snapshotTagModify('src', 'dst', force=True, remove=True)

        # tests
        self._create_tag.assert_not_called()
        self.get_tag.assert_has_calls([
            mock.call('src', event=None, strict=True),
            mock.call('dst', strict=True),
            mock.call(dst['id'], strict=True),
        ])

        self.get_user.assert_called_once_with(user['id'], strict=True)
        self.edit_tag.assert_called_once_with(dst['id'], parent=None, arches=src['arches'],
                                              perm=src['perm_id'], locked=src['locked'],
                                              maven_support=src['maven_support'],
                                              maven_include_all=src['maven_include_all'],
                                              extra=src['extra'], remove_extra=[])
        self.hub.listPackages.assert_has_calls([
            mock.call(tagID=src['id'], event=None, inherited=True),
            mock.call(tagID=dst['id'], inherited=True)
        ])
        self._direct_pkglist_add.assert_has_calls([
            # remove additional package
            mock.call(dst,
                      pkg2['package_name'],
                      owner=pkg2['owner_name'],
                      block=True,
                      extra_arches=pkg2['extra_arches'],
                      force=True,
                      update=True),
            # add missing package
            mock.call(dst,
                      pkg1['package_name'],
                      owner=pkg1['owner_name'],
                      block=pkg1['blocked'],
                      extra_arches=pkg1['extra_arches'],
                      force=True,
                      update=False),
        ])
        self.readTaggedBuilds.assert_has_calls([
            mock.call(src['id'], event=None, inherit=True, latest=True),
            mock.call(dst['id'], inherit=False, latest=False),
        ])
        self._direct_untag_build.assert_not_called()
        self._untag_build.assert_called_once_with('dst', build2, force=True)
        self._direct_tag_build.assert_called_once_with(dst, build, user, force=True)
        self._grp_pkg_add.assert_called_once_with('dst', 'group1', pkg1['package_name'],
                                                  block=False, force=True)
        self._grp_req_add.assert_has_calls([
            mock.call('dst', 'group1', 'group5', block=False, force=True),
            mock.call('dst', 'group1', 'group4', block=True, force=True),
        ])
        self._grplist_add.assert_has_calls([
            mock.call(dst['id'], 'group2', block=False, force=True),
            mock.call(dst['id'], 'group1', block=False, force=True, opts=src_group1),
        ])
        self._grplist_remove.assert_not_called()
        self.hub.massTag.assert_not_called()
