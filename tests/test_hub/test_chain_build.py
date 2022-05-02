import unittest
import koji
import kojihub
import mock


class TestChainBuild(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        self.exports = kojihub.RootExports()
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.hasPerm = mock.MagicMock()
        self.get_channel = mock.patch('kojihub.get_channel').start()
        self.make_task = mock.patch('kojihub.make_task').start()
        self.srcs = ['pkg1']
        self.target = 'test-target'

    def tearDown(self):
        mock.patch.stopall()

    def test_srcs_wrong_type(self):
        srcs = 'pkg'
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.chainBuild(srcs, self.target)
        self.assertEqual(f"Invalid type for value '{srcs}': {type(srcs)}", str(cm.exception))

    def test_priority_without_admin(self):
        priority = -10
        self.context.session.hasPerm.return_value = False
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.chainBuild(self.srcs, self.target, priority=priority)
        self.assertEqual("only admins may create high-priority tasks", str(cm.exception))

    def test_channel_not_str(self):
        priority = 10
        self.get_channel.return_value = {'comment': None, 'description': None, 'enabled': True,
                                         'id': 2, 'name': 'maven'}
        self.make_task.return_value = 123
        self.exports.chainBuild(self.srcs, self.target, priority=priority, channel=2)
