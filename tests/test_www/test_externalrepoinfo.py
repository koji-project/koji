import mock
import unittest

from .loadwebindex import webidx


class TestExternalRepoInfo(unittest.TestCase):
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
        self.extrepo_id = '111'

    def tearDown(self):
        mock.patch.stopall()

    def test_externalrepoinfo_valid(self):
        """Test externalrepoinfo function."""
        self.get_server.return_value = self.server
        self.server.getExternalRepo.return_value = {'name': 'ext-repo', 'id': 111}
        self.server.getTagExternalRepos.return_value = {'id': 1, 'name': 'test-tag'}
        webidx.externalrepoinfo(self.environ, self.extrepo_id)
        self.server.getExternalRepo.assert_called_once_with(int(self.extrepo_id), strict=True)
        self.server.getTagExternalRepos.assert_called_once_with(repo_info=int(self.extrepo_id))
