import unittest
import koji
import kojihub
import mock


class TestBuild(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        self.exports = kojihub.RootExports()
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.hasPerm = mock.MagicMock()
        self.get_channel = mock.patch('kojihub.get_channel').start()
        self.make_task = mock.patch('kojihub.make_task').start()
        self.src = 'test-src'
        self.target = 'test-target'

    def tearDown(self):
        mock.patch.stopall()

    def test_src_wrong_type(self):
        src = ['test-priority']
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.build(src, self.target)
        self.assertEqual(f"Invalid type for value '{src}': {type(src)}", str(cm.exception))

    def test_priority_without_admin(self):
        priority = -10
        self.context.session.hasPerm.return_value = False
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.build(self.src, self.target, priority=priority)
        self.assertEqual("only admins may create high-priority tasks", str(cm.exception))

    def test_channel_not_str(self):
        priority = 10
        self.get_channel.return_value = {'comment': None, 'description': None, 'enabled': True,
                                         'id': 2, 'name': 'maven'}
        self.make_task.return_value = 123
        self.exports.build(self.src, self.target, priority=priority, channel=2)
