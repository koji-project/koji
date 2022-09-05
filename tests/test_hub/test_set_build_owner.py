import mock
import unittest

import kojihub

UP = kojihub.UpdateProcessor


class TestSetBuildOwner(unittest.TestCase):

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.UpdateProcessor = mock.patch('kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.context = mock.patch('kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.assertPerm = mock.MagicMock()
        self.exports = kojihub.RootExports()
        self.get_build = mock.patch('kojihub.get_build').start()
        self.get_user = mock.patch('kojihub.get_user').start()
        self.run_callbacks = mock.patch('koji.plugin.run_callbacks').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_set_build_owner(self):
        self.get_build.return_value = {'id': 123, 'owner_id': 1}
        self.get_user.return_value = {'id': 2}
        self.context.event_id = 42
        self.context.session.user_id = 23
        self.exports.setBuildOwner('test-build', 'test-user')
        clauses = ['id=%(buildid)i']
        data = {'owner': 2}
        values = {'buildid': 123}
        update = self.updates[0]
        self.assertEqual(update.table, 'build')
        self.assertEqual(update.data, data)
        self.assertEqual(update.rawdata, {})
        self.assertEqual(update.clauses, clauses)
        self.assertEqual(update.values, values)
