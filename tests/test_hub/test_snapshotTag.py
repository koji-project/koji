from unittest import mock
import unittest
import koji
import kojihub


class TestSnapshotTag(unittest.TestCase):
    def setUp(self):
        self._create_tag = mock.patch('kojihub.kojihub._create_tag').start()
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self._direct_tag_build = mock.patch('kojihub.kojihub._direct_tag_build').start()
        self._direct_pkglist_add = mock.patch('kojihub.kojihub._direct_pkglist_add').start()
        self._delete_event_id = mock.patch('kojihub.kojihub._delete_event_id').start()
        self._grplist_add = mock.patch('kojihub.kojihub._grplist_add').start()
        self._grp_pkg_add = mock.patch('kojihub.kojihub._grp_pkg_add').start()
        self._grp_req_add = mock.patch('kojihub.kojihub._grp_req_add').start()
        self.readTagGroups = mock.patch('kojihub.kojihub.readTagGroups').start()
        self.readTaggedBuilds = mock.patch('kojihub.kojihub.readTaggedBuilds').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.hub = kojihub.RootExports()
        self.hub.listPackages = mock.MagicMock()
        self.hub.massTag = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_no_permission(self):
        self.context.session.assertPerm.side_effect = koji.ActionNotAllowed
        with self.assertRaises(koji.ActionNotAllowed):
            self.hub.snapshotTag('src', 'dst')
        self.context.session.assertPerm.assert_called_once_with('tag')

    def test_builds_without_pkgs(self):
        with self.assertRaises(koji.ParameterError):
            self.hub.snapshotTag('src', 'dst', builds=True, pkgs=False)

    def test_existing_dst(self):
        self.get_tag.side_effect = [{'id': 1}, {'id': 2}]
        with self.assertRaises(koji.GenericError) as cm:
            self.hub.snapshotTag('src', 'dst')
        self.assertEqual("Target tag already exists", str(cm.exception))

    def test_locked_without_force(self):
        self.get_tag.side_effect = [None, {'id': 1, 'locked': True}]
        with self.assertRaises(koji.GenericError) as cm:
            self.hub.snapshotTag('src', 'dst')
        self.assertEqual("Source tag is locked, use force to copy", str(cm.exception))

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
        pkg = {
            'package_name': 'pkg1',
            'owner_name': 'owner',
            'blocked': False,
            'extra_arches': None,
        }
        build = {
            'id': 21,
            'nvr': 'n-v-r',
        }

        self.get_tag.side_effect = [
            None,  # non-existing dst
            src,  # retrieve src
            dst,  # retrieve created dst
        ]
        self._create_tag.return_value = dst['id']
        self.hub.listPackages.return_value = [pkg]
        self.readTaggedBuilds.return_value = [build]
        self.readTagGroups.return_value = [
            {
                'id': 1,
                'name': 'group',
                'blocked': False,
                'packagelist': [{'package': 'pkg', 'blocked': False}],
                'grouplist': [{'name': 'group2', 'blocked': False}],
            }
        ]

        # call
        self.hub.snapshotTag('src', 'dst', force=True)

        self._create_tag.assert_called_once_with('dst', parent=None, arches=src['arches'],
                                                 perm=src['perm_id'], locked=src['locked'],
                                                 maven_support=src['maven_support'],
                                                 maven_include_all=src['maven_include_all'],
                                                 extra=src['extra'])
        self.get_tag.assert_has_calls([
            mock.call('dst'),
            mock.call('src', event=None, strict=True),
            mock.call(dst['id'], strict=True),
        ])
        self.hub.listPackages.assert_called_once_with(tagID=src['id'], event=None, inherited=True)
        self._direct_pkglist_add.assert_called_once_with(
            taginfo=dst['id'],
            pkginfo=pkg['package_name'],
            owner=pkg['owner_name'],
            block=pkg['blocked'],
            extra_arches=pkg['extra_arches'],
            force=True,
            update=False,
        )
        self.readTaggedBuilds.assert_called_once_with(tag=src['id'], inherit=True, event=None, latest=True)
        self.hub.massTag.assert_called_once_with(dst['id'], [build])
