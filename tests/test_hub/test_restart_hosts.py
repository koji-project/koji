import unittest

import mock

import kojihub


class TestRestartHosts(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.make_task = mock.patch('kojihub.make_task').start()

    def options_is_none(self):
        self.make_task.return_value = 13
        rv = self.exports.restartHosts()
        self.assertEqual(rv, 13)

    def options_is_not_none(self):
        self.make_task.return_value = 13
        rv = self.exports.restartHosts(options={'opt': 'open'})
        self.assertEqual(rv, 13)
