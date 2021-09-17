import unittest

import mock

import koji
import kojihub


class TestGetExternalRepo(unittest.TestCase):

    def setUp(self):
        self.get_external_repos = mock.patch('kojihub.get_external_repos').start()
        self.exports = kojihub.RootExports()

    def test_non_exist_repo_with_strict(self):
        repo = 'test-repo'
        self.get_external_repos.return_value = []
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getExternalRepo(repo, strict=True)
        self.assertEqual("No such repo: %s" % repo, str(cm.exception))

    def test_non_exist_repo_without_strict(self):
        repo = 'test-repo'
        self.get_external_repos.return_value = []
        rv = self.exports.getExternalRepo(repo, strict=False)
        self.assertEqual(None, rv)

    def test_valid(self):
        repo = 'test-repo'
        repo_info = [
            {'id': 1,
             'name': 'build-external-repo-1',
             'url': 'https://path/to/ext/repo1'},
        ]
        self.get_external_repos.return_value = repo_info
        rv = self.exports.getExternalRepo(repo, strict=True)
        self.assertEqual(repo_info[0], rv)

    def test_more_repos(self):
        repo = 'test-repo'
        repo_info = [
            {'id': 1,
             'name': 'build-external-repo-1',
             'url': 'https://path/to/ext/repo1'},
            {'id': 2,
             'name': 'build-external-repo-1',
             'url': 'https://path/to/ext/repo2'}
        ]
        self.get_external_repos.return_value = repo_info
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getExternalRepo(repo, strict=False)
        self.assertEqual("More than one repo in the result.", str(cm.exception))
