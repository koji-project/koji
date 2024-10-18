import unittest
import koji

from unittest import mock
from .loadwebindex import webidx


class TestBuildrootInfo(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.gen_html = mock.patch.object(webidx, '_genHTML').start()
        self.assert_login = mock.patch.object(webidx, "_assertLogin").start()
        self.server = mock.MagicMock()
        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': None
        }
        self.buildroot_id = '1'

    def tearDown(self):
        mock.patch.stopall()

    def test_buildrootinfo_exception(self):
        """Test buildrootinfo function raises exception when buildroot ID is unknown."""
        self.get_server.return_value = self.server
        self.server.getBuildroot.return_value = None

        with self.assertRaises(koji.GenericError) as cm:
            webidx.buildrootinfo(self.environ, self.buildroot_id)
        self.assertEqual(str(cm.exception), f'unknown buildroot ID: {self.buildroot_id}')

    def test_buildrootinfo_valid(self):
        """Test buildrootinfo function."""
        self.get_server.return_value = self.server
        self.server.getBuildroot.return_value = {'br_type': 55, 'cg_name': 'test-test',
                                                 'id': int(self.buildroot_id)}
        webidx.buildrootinfo(self.environ, self.buildroot_id)
        self.server.getBuildroot.assert_called_once_with(int(self.buildroot_id))
        self.server.getTaskInfo.assert_not_called()

    def test_buildrootinfo_valid_2(self):
        """Test buildrootinfo function."""
        self.get_server.return_value = self.server
        self.server.getBuildroot.return_value = {'br_type': 0, 'task_id': 345,
                                                 'tag_name': 'test-tag', 'repo_id': 999,
                                                 'id': int(self.buildroot_id)}
        self.server.getTaskInfo.return_value = {'id': 345}
        webidx.buildrootinfo(self.environ, self.buildroot_id)
        self.server.getBuildroot.assert_called_once_with(int(self.buildroot_id))
        self.server.getTaskInfo.assert_called_once_with(345, request=True)
