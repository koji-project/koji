from unittest import mock
import unittest

import kojihub
import koji

UP = kojihub.UpdateProcessor


class TestSetBuildTimestamp(unittest.TestCase):

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.assertPerm = mock.MagicMock()
        self.exports = kojihub.RootExports()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.run_callbacks = mock.patch('koji.plugin.run_callbacks').start()
        self.buildinfo_old = {'completion_ts': 1671466000.613543, 'id': 111}
        self.buildinfo_new = {'completion_ts': 1671468684.613543, 'id': 111}

    def tearDown(self):
        mock.patch.stopall()

    def test_ts_not_correct_type(self):
        build_id = 111
        ts = 'wrong-type-ts'
        self.get_build.return_value = self.buildinfo_old
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.setBuildTimestamp(build_id, ts)
        self.assertEqual("Invalid type for timestamp", str(cm.exception))

    def test_valid(self):
        build_id = 111
        ts = 1671468684.613543
        self.get_build.side_effect = [self.buildinfo_old, self.buildinfo_new]
        self.exports.setBuildTimestamp(build_id, ts)
        update = self.updates[0]
        self.assertEqual(update.table, 'build')
        self.assertEqual(update.data, {})
        self.assertEqual(update.rawdata, {
            'completion_time':
                f"TIMESTAMP 'epoch' AT TIME ZONE 'utc' + '{ts:f} seconds'::interval"})
        self.assertEqual(update.clauses, ['id = %(buildid)i'])
        self.assertEqual(update.values, {'buildid': build_id})
