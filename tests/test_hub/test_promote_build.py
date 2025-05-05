import datetime
import os.path
import tempfile
from unittest import mock
import unittest

import koji
import kojihub


UP = kojihub.UpdateProcessor


class TestPromoteBuild(unittest.TestCase):

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertLogin = mock.MagicMock()
        self.user = {'id': 1, 'name': 'jdoe'}
        self.get_user = mock.patch('kojihub.kojihub.get_user', return_value=self.user).start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.assert_policy = mock.patch('kojihub.kojihub.assert_policy').start()
        self.apply_volume_policy = mock.patch('kojihub.kojihub.apply_volume_policy',
                                              return_value=None).start()
        self.safer_move = mock.patch('kojihub.kojihub.safer_move').start()
        self.ensure_volume_symlink = mock.patch('kojihub.kojihub.ensure_volume_symlink').start()
        self.ensure_volume_backlink = mock.patch('kojihub.kojihub.ensure_volume_backlink').start()
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name',
                                      return_value={'id': 1, 'name': 'DEFAULT'}).start()
        self.os_symlink = mock.patch('os.symlink').start()
        self.list_tags = mock.patch('kojihub.kojihub.list_tags',
                                    return_value=[{'id': 101}]).start()
        self.set_tag_update = mock.patch('kojihub.kojihub.set_tag_update').start()
        self._now = datetime.datetime.now()
        self._datetime = mock.patch('kojihub.kojihub.datetime.datetime').start()
        self.now = self._datetime.now = mock.MagicMock(return_value=self._now)

        self.draft_build = {
            'id': 1,
            'name': 'foo',
            'version': 'bar',
            'release': 'tgtrel,draft_1',
            'nvr': 'testnvr',
            'state': 1,
            'draft': True,
            'volume_id': 99,
            'volume_name': 'X',
            'task_id': 222
        }

        self.new_build = {
            # no check on the info
            'id': 1,
            'name': 'foo',
            'version': 'bar',
            'release': 'tgtrel',
            'volume_name': 'X'
        }

    def tearDown(self):
        mock.patch.stopall()

    def test_promote_build_valid(self):
        self.get_build.side_effect = [
            self.draft_build,
            None,
            self.new_build
        ]

        ret = self.exports.promoteBuild('a-draft-build')
        self.assertEqual(ret, self.new_build)
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'build')
        self.assertEqual(update.values, self.draft_build)
        self.assertEqual(update.data, {'draft': False,
                                       'promoter': self.user['id'],
                                       'release': 'tgtrel'})
        self.assertEqual(update.rawdata, {'promotion_time': 'now()'})
        self.assertEqual(update.clauses, ['id=%(id)i'])
        self.apply_volume_policy.assert_called_once_with(
            self.new_build, strict=False
        )
        self.safer_move.assert_called_once_with(
            '/mnt/koji/vol/X/packages/foo/bar/tgtrel,draft_1',
            '/mnt/koji/vol/X/packages/foo/bar/tgtrel'
        )
        self.os_symlink.assert_not_called()

    def test_promote_build_not_draft(self):
        self.get_build.return_value = {'draft': False, 'nvr': 'testnvr'}

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.promoteBuild('a-regular-build')
        self.assertEqual(
            str(cm.exception),
            "Cannot promote build testnvr. Reason: Not a draft build"
        )
        self.assertEqual(len(self.updates), 0)

    def test_promote_build_target_release(self):
        draft = {
            'id': 1,
            'name': 'foo',
            'version': 'bar',
            # bad delimiter
            'release': 'tgtrel@draft_1',
            'nvr': 'testnvr',
            'state': 1,
            'draft': True,
            'volume_id': 99,
            'volume_name': 'X',
            'task_id': 222
        }

        self.get_build.return_value = draft

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.promoteBuild('a-regular-build')
        self.assertEqual(
            str(cm.exception),
            "draft release: tgtrel@draft_1 is not in valid format"
        )
        self.assertEqual(len(self.updates), 0)

    def test_promote_build_not_completed(self):
        draft = {
            'id': 1,
            'name': 'foo',
            'version': 'bar',
            'release': 'tgtrel#draft_1',
            'nvr': 'testnvr',
            'draft': True,
            'state': 0,
            'volume_id': 99,
            'volume_name': 'X',
            'task_id': 222
        }

        self.get_build.return_value = draft

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.promoteBuild('a-regular-build')
        self.assertEqual(
            str(cm.exception),
            f"Cannot promote build {draft['nvr']}. Reason: state (BUILDING) is not COMPLETE."
        )
        self.assertEqual(len(self.updates), 0)

    def test_promote_build_target_build_exists(self):
        old = {
            'id': 'any',
            'nvr': 'oldnvr'
        }
        self.get_build.side_effect = [self.draft_build, old]

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.promoteBuild('a-regular-build')
        self.assertEqual(
            str(cm.exception),
            "Cannot promote build testnvr. Reason: Target build exists: oldnvr(#any)"
        )
        self.assertEqual(len(self.updates), 0)
        self.get_build.assert_called_with({
            'name': 'foo',
            'version': 'bar',
            'release': 'tgtrel'
        }, strict=False)


class TestPromoteBuildFiles(unittest.TestCase):
    # these tests use a tempdir

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        # set up our dirs
        self.tempdir = tempfile.mkdtemp()
        self.topdir = self.tempdir + '/koji'
        self.pathinfo = koji.PathInfo(self.topdir)
        mock.patch('koji.pathinfo', new=self.pathinfo).start()
        # separate dir for volume X
        vol_x = self.tempdir + '/vol_X'
        koji.ensuredir(vol_x)
        voldir = self.pathinfo.volumedir('X')
        koji.ensuredir(os.path.dirname(voldir))  # koji/vol
        os.symlink(vol_x, voldir)

        self.exports = kojihub.RootExports()
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertLogin = mock.MagicMock()
        self.user = {'id': 1, 'name': 'jdoe'}
        self.get_user = mock.patch('kojihub.kojihub.get_user', return_value=self.user).start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.assert_policy = mock.patch('kojihub.kojihub.assert_policy').start()
        self.apply_volume_policy = mock.patch('kojihub.kojihub.apply_volume_policy',
                                              return_value=None).start()
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name',
                                      return_value={'id': 1, 'name': 'DEFAULT'}).start()
        self.list_tags = mock.patch('kojihub.kojihub.list_tags',
                                    return_value=[{'id': 101}]).start()
        self.set_tag_update = mock.patch('kojihub.kojihub.set_tag_update').start()
        self._now = datetime.datetime.now()
        self._datetime = mock.patch('kojihub.kojihub.datetime.datetime').start()
        self.now = self._datetime.now = mock.MagicMock(return_value=self._now)

        self.draft_build = {
            'id': 1,
            'name': 'foo',
            'version': 'bar',
            'release': 'tgtrel,draft_1',
            'nvr': 'testnvr',
            'state': 1,
            'draft': True,
            'volume_id': 99,
            'volume_name': 'X',
            'task_id': 222
        }

        self.new_build = {
            # no check on the info
            'id': 1,
            'name': 'foo',
            'version': 'bar',
            'release': 'tgtrel',
            'volume_name': 'X'
        }

    def tearDown(self):
        mock.patch.stopall()

    def test_promote_build_volume_link(self):
        self.get_build.side_effect = [
            self.draft_build,
            None,
            self.new_build
        ]
        orig_bdir = self.pathinfo.build(self.draft_build)
        koji.ensuredir(orig_bdir)
        sentinel = 'HELLO 873\n'
        with open(orig_bdir + '/sentinel.txt', 'wt') as fp:
            fp.write(sentinel)

        # promote
        ret = self.exports.promoteBuild('a-draft-build')

        self.assertEqual(ret, self.new_build)
        # orig_bdir should be a symlink
        assert os.path.islink(orig_bdir)
        # should be accessible via original path
        with open(orig_bdir + '/sentinel.txt', 'rt') as fp:
            assert fp.read() == sentinel


# the end
