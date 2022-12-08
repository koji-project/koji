import unittest

import mock

import koji
import kojihub


class TestRestartHosts(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.make_task = mock.patch('kojihub.kojihub.make_task').start()

    def test_options_is_none(self):
        self.make_task.return_value = 13
        rv = self.exports.restartHosts()
        self.assertEqual(rv, 13)

    def test_options_is_not_none(self):
        self.make_task.return_value = 13
        rv = self.exports.restartHosts(options={'opt': 'open'})
        self.assertEqual(rv, 13)

    def test_options_wrong_type(self):
        options = 'test-options'
        with self.assertRaises(koji.ParameterError) as ex:
            self.exports.restartHosts(options=options)
        self.assertEqual(f"Invalid type of options: {type(options)}", str(ex.exception))
