import unittest
import koji
import kojihub
import mock


class TestWrapperRPM(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        self.exports = kojihub.RootExports()
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.hasPerm = mock.MagicMock()
        self.get_channel = mock.patch('kojihub.get_channel').start()
        self.exports.getBuild = mock.MagicMock()
        self.make_task = mock.patch('kojihub.make_task').start()
        self.list_rpms = mock.patch('kojihub.list_rpms').start()
        self.exports.getTag = mock.MagicMock()
        self.exports.getBuildTarget = mock.MagicMock()
        self.exports.getRepo = mock.MagicMock()
        self.build = 'testbuild-1-1.4'
        self.target = 'test-target'
        self.url = 'https://test-url.com'
        self.buildinfo = {'name': 'testbuild', 'version': '1', 'release': '1.4',
                          'nvr': self.build, 'id': 123}
        self.targetinfo = {'build_tag': 444,
                           'build_tag_name': 'test-tag',
                           'dest_tag': 445,
                           'dest_tag_name': 'dest-test-tag',
                           'id': 1,
                           'name': self.target}
        self.taginfo = {'id': 159, 'name': 'test-tag'}
        self.repoinfo = {'id': 753}

    def tearDown(self):
        mock.patch.stopall()

    def test_url_wrong_type(self):
        url = ['test-url']
        self.context.opts.get.return_value = True
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.wrapperRPM(self.build, url, self.target)
        self.assertEqual(f"Invalid type for value '{url}': {type(url)}", str(cm.exception))

    def test_channel_not_str(self):
        priority = 10
        self.context.opts.get.return_value = True
        self.exports.getBuild.return_value = self.buildinfo
        self.list_rpms.return_value = []
        self.exports.getBuildTarget.return_value = self.targetinfo
        self.exports.getRepo.return_value = self.taginfo
        self.exports.getRepo.return_value = self.repoinfo
        self.make_task.return_value = 123
        self.get_channel.return_value = {'comment': None, 'description': None, 'enabled': True,
                                         'id': 2, 'name': 'maven'}
        with self.assertRaises(koji.ParameterError):
            self.exports.wrapperRPM(self.build, self.url, self.target,
                                    priority=priority, channel=2)
