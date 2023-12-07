import datetime
import json
import mock
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
        self.move_and_symlink = mock.patch('kojihub.kojihub.move_and_symlink').start()
        self.ensure_volume_symlink = mock.patch('kojihub.kojihub.ensure_volume_symlink').start()
        self.list_tags = mock.patch('kojihub.kojihub.list_tags',
                                    return_value=[{'id': 101}]).start()
        self.set_tag_update = mock.patch('kojihub.kojihub.set_tag_update').start()
        self.encode_datetime = mock.patch(
            'kojihub.kojihub.encode_datetime', return_value='NOW'
        ).start()
        self._now = datetime.datetime.now()
        self._datetime = mock.patch('kojihub.kojihub.datetime.datetime').start()
        self.now = self._datetime.now = mock.MagicMock(return_value=self._now)

        self.draft_build = {
            'id': 1,
            'name': 'foo',
            'version': 'bar',
            'release': 'tgtrel,draft_1',
            'nvr': 'testnvr',
            'extra': {
                'draft': {
                    'promoted': False,
                    'target_release': 'tgtrel'
                }},
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

        extra = json.dumps(
            {
                'draft': {
                    'promoted': True,
                    'target_release': 'tgtrel',
                    'old_release': 'tgtrel,draft_1',
                    'promotion_time': 'NOW',
                    'promotion_ts': self._now.timestamp(),
                    'promoter': self.user['name']
                }
            }
        )

        ret = self.exports.promoteBuild('a-draft-build', strict=True)
        self.assertEqual(ret, self.new_build)
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'build')
        self.assertEqual(update.values, self.draft_build)
        self.assertEqual(update.data, {'draft': False,
                                       'release': 'tgtrel',
                                       'extra': extra})
        self.assertEqual(update.rawdata, {})
        self.assertEqual(update.clauses, ['id=%(id)i'])
        self.apply_volume_policy.assert_called_once_with(
            self.new_build, strict=False
        )

    def test_promote_build_not_draft(self):
        self.get_build.return_value = {'draft': False}

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.promoteBuild('a-regular-build', strict=True)
        self.assertEqual(str(cm.exception), "Not a draft build: {'draft': False}")
        self.assertEqual(len(self.updates), 0)

        ret = self.exports.promoteBuild('a-regular-build', strict=False)
        self.assertIsNone(ret)
        self.assertEqual(len(self.updates), 0)

    def test_promote_build_target_release(self):
        draft = {
            'id': 1,
            'name': 'foo',
            'version': 'bar',
            # bad delimiter
            'release': 'tgtrel@draft_1',
            'extra': {
                'draft': {
                    'promoted': False,
                    # target_release doesn't matter now
                    'target_release': 'any'
                }},
            'state': 1,
            'draft': True,
            'volume_id': 99,
            'volume_name': 'X',
            'task_id': 222
        }

        self.get_build.return_value = draft

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.promoteBuild('a-regular-build', strict=True)
        self.assertEqual(
            str(cm.exception),
            "draft release: tgtrel@draft_1 is not in valid format"
        )
        self.assertEqual(len(self.updates), 0)

        ret = self.exports.promoteBuild('a-regular-build', strict=False)
        self.assertIsNone(ret)
        self.assertEqual(len(self.updates), 0)

    def test_promote_build_not_completed(self):
        draft = {
            'id': 1,
            'name': 'foo',
            'version': 'bar',
            'release': 'tgtrel#draft_1',
            'nvr': 'testnvr',
            'extra': {
                'draft': {
                    'promoted': False,
                    'target_release': 'any'
                }},
            'draft': True,
            'state': 0,
            'volume_id': 99,
            'volume_name': 'X',
            'task_id': 222
        }

        self.get_build.return_value = draft

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.promoteBuild('a-regular-build', strict=True)
        self.assertEqual(
            str(cm.exception),
            f"Cannot promote build - {draft['nvr']}. Reason: state (BUILDING) is not COMPLETE."
        )
        self.assertEqual(len(self.updates), 0)

        ret = self.exports.promoteBuild('a-regular-build', strict=False)
        self.assertIsNone(ret)
        self.assertEqual(len(self.updates), 0)

    def test_promote_build_target_build_exists(self):
        old = {
            'id': 'any'
        }
        self.get_build.side_effect = [self.draft_build, old]

        with self.assertRaises(koji.GenericError) as cm:
            self.exports.promoteBuild('a-regular-build', strict=True)
        self.assertEqual(str(cm.exception), f"Target build already exists: {old}")
        self.assertEqual(len(self.updates), 0)
        self.get_build.assert_called_with({
            'name': 'foo',
            'version': 'bar',
            'release': 'tgtrel'
        })

        self.get_build.reset_mock()
        self.get_build.side_effect = [self.draft_build, old]
        ret = self.exports.promoteBuild('a-regular-build', strict=False)
        self.assertIsNone(ret)
        self.assertEqual(len(self.updates), 0)
