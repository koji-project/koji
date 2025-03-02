from unittest import mock
import unittest

import koji
from .loadwebindex import webidx


class TestRepoInfo(unittest.TestCase):
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
        self.repo_id = '5'

    def tearDown(self):
        mock.patch.stopall()

    def test_repoinfo_dist(self):
        """Test repoinfo function - dist repo"""
        self.get_server.return_value = self.server

        self.server.repoInfo.return_value = {'dist': True, 'id': int(self.repo_id),
                                             'tag_name': 'test-tag', 'state': koji.REPO_READY,
                                             'create_ts': 1735707600.0}
        self.server.listBuildroots.return_value = []

        webidx.repoinfo(self.environ, self.repo_id)
        self.server.repoInfo.assert_called_once_with(int(self.repo_id), strict=False)
        self.server.listBuildroots.assert_called_once_with(repoID=int(self.repo_id))

    def test_repoinfo_not_dist(self):
        """Test repoinfo function - not dist repo"""
        self.get_server.return_value = self.server

        self.server.repoInfo.return_value = {'dist': False, 'id': int(self.repo_id),
                                             'tag_name': 'test-tag', 'state': koji.REPO_READY,
                                             'create_ts': 1735707600.0}
        self.server.listBuildroots.return_value = [{'id': 1, 'repo_id': int(self.repo_id)}]

        webidx.repoinfo(self.environ, self.repo_id)
        self.server.repoInfo.assert_called_once_with(int(self.repo_id), strict=False)
        self.server.listBuildroots.assert_called_once_with(repoID=int(self.repo_id))
