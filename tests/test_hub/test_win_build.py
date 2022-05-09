import unittest
import koji
import kojihub
import mock


class TestWinBuild(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        self.exports = kojihub.RootExports()
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.hasPerm = mock.MagicMock()
        self.get_channel = mock.patch('kojihub.get_channel').start()
        self.assert_policy = mock.patch('kojihub.assert_policy').start()
        self.get_build_target = mock.patch('kojihub.get_build_target').start()
        self.make_task = mock.patch('kojihub.make_task').start()
        self.vm = 'test-vm'
        self.url = 'https://test-url.com'
        self.target = 'test-target'
        self.targetinfo = {'build_tag': 444,
                           'build_tag_name': 'test-tag',
                           'dest_tag': 445,
                           'dest_tag_name': 'dest-test-tag',
                           'id': 1,
                           'name': self.target}

    def tearDown(self):
        mock.patch.stopall()

    def test_win_not_supported(self):
        self.context.opts.get.return_value = False
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.winBuild(self.vm, self.url, self.target)
        self.assertEqual("Windows support not enabled", str(cm.exception))

    def test_vm_wrong_type(self):
        vm = ['test-vm']
        self.context.opts.get.return_value = True
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.winBuild(vm, self.url, self.target)
        self.assertEqual(f"Invalid type for value '{vm}': {type(vm)}, "
                         f"expected type <class 'str'>", str(cm.exception))

    def test_url_wrong_type(self):
        url = ['test-url']
        self.context.opts.get.return_value = True
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.winBuild(self.vm, url, self.target)
        self.assertEqual(f"Invalid type for value '{url}': {type(url)}, "
                         f"expected type <class 'str'>", str(cm.exception))

    def test_priority_without_admin(self):
        priority = -10
        self.context.opts.get.return_value = True
        self.get_build_target.return_value = self.targetinfo
        self.assert_policy.return_value = True
        self.context.session.hasPerm.return_value = False
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.winBuild(self.vm, self.url, self.target, priority=priority)
        self.assertEqual("only admins may create high-priority tasks", str(cm.exception))

    def test_channel_not_str(self):
        self.context.opts.get.return_value = True
        self.get_build_target.return_value = self.targetinfo
        self.assert_policy.return_value = True
        self.make_task.return_value = 123
        self.get_channel.return_value = {'comment': None, 'description': None, 'enabled': True,
                                         'id': 1, 'name': 'vm'}
        self.exports.winBuild(self.vm, self.url, self.target, channel=1, priority=10)
