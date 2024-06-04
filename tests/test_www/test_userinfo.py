import mock
import unittest

from .loadwebindex import webidx


class TestUserInfo(unittest.TestCase):
    def setUp(self):
        self.get_server = mock.patch.object(webidx, "_getServer").start()
        self.gen_html = mock.patch.object(webidx, '_genHTML').start()
        self.server = mock.MagicMock()
        self.environ = {
            'koji.options': {
                'SiteName': 'test',
                'KojiFilesURL': 'https://server.local/files',
            },
            'koji.currentUser': None
        }
        self.user_id = '5'

    def tearDown(self):
        mock.patch.stopall()

    def test_userinfo(self):
        """Test userinfo function"""
        self.get_server.return_value = self.server

        self.server.getUser.return_value = {'id': int(self.user_id), 'name': 'test-user'}
        self.server.listTasks.return_value = 123
        self.server.countAndFilterResults.return_value = [123, 'result']

        webidx.userinfo(self.environ, self.user_id)
        self.server.getUser.assert_called_once_with(int(self.user_id), strict=True)
        self.server.listTasks.assert_called_once_with(
            opts={'owner': int(self.user_id), 'parent': None}, queryOpts={'countOnly': True})
