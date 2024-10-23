import unittest
import koji
import kojihub
from unittest import mock


class TestChainMaven(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.exports = kojihub.RootExports()
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.hasPerm = mock.MagicMock()
        self.get_channel = mock.patch('kojihub.kojihub.get_channel').start()
        self.make_task = mock.patch('kojihub.kojihub.make_task').start()
        self.builds = {'build1': {}, 'build2': {}, 'build3': {}}
        self.target = 'test-target'

    def tearDown(self):
        mock.patch.stopall()

    def test_maven_not_supported(self):
        self.context.opts.get.return_value = False
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.chainMaven(self.builds, self.target)
        self.assertEqual("Maven support not enabled", str(cm.exception))

    def test_builds_wrong_type(self):
        builds = 'test-builds'
        self.context.opts.get.return_value = True
        with self.assertRaises(koji.ParameterError) as cm:
            self.exports.chainMaven(builds, self.target)
        self.assertEqual(f"Invalid type for value '{builds}': {type(builds)}, "
                         f"expected type <class 'dict'>", str(cm.exception))

    def test_priority_without_admin(self):
        priority = -10
        self.context.opts.get.return_value = True
        self.context.session.hasPerm.return_value = False
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.chainMaven(self.builds, self.target, priority=priority)
        self.assertEqual("only admins may create high-priority tasks", str(cm.exception))

    def test_channel_not_str(self):
        self.context.opts.get.return_value = True
        self.make_task.return_value = 123
        self.get_channel.return_value = {'comment': None, 'description': None, 'enabled': True,
                                         'id': 2, 'name': 'maven'}
        self.exports.chainMaven(self.builds, self.target, channel=2, priority=10)
