import unittest

import mock

import koji
import kojihub


UP = kojihub.UpdateProcessor


class TestDeleteBuildTarget(unittest.TestCase):

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.lookup_build_target = mock.patch('kojihub.kojihub.lookup_build_target').start()
        self.exports = kojihub.RootExports()
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.context_db = mock.patch('kojihub.db.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context_db.session.assertLogin = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_non_exist_target(self):
        build_target = 'build-target'
        self.lookup_build_target.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.deleteBuildTarget(build_target)
        self.assertEqual("No such build target: %s" % build_target, str(cm.exception))
        self.assertEqual(len(self.updates), 0)

    def test_valid(self):
        build_target = 'build-target'
        self.context_db.event_id = 42
        self.context_db.session.user_id = 23
        self.lookup_build_target.return_value = {'id': 123}
        self.exports.deleteBuildTarget(build_target)

        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'build_target_config')
        self.assertEqual(update.clauses, ["build_target_id = %(targetID)i", 'active = TRUE'])
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 23})
        self.assertEqual(update.rawdata, {'active': 'NULL'})
