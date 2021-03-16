import unittest

import mock

import koji
import kojihub


class TestGetExternalRepo(unittest.TestCase):

    def setUp(self):
        self.get_external_repos = mock.patch('kojihub.get_external_repos').start()
        self.exports = kojihub.RootExports()

    def test_non_exist_repo(self):
        repo = 'test-repo'
        self.get_external_repos.return_value = []
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getExternalRepo(repo, strict=True)
        self.assertEqual("No such repo: %s" % repo, str(cm.exception))
