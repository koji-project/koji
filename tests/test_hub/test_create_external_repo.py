# coding: utf-8
import unittest

import mock

import koji
import kojihub


class TestCreateExternalRepo(unittest.TestCase):

    def setUp(self):
        self.get_external_repos = mock.patch('kojihub.kojihub.get_external_repos').start()
        self.verify_name_internal = mock.patch('kojihub.kojihub.verify_name_internal').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()
        self.repo_url = 'http://path_to_ext_repo.com'
        self.repo_name = 'test-repo'
        self.repo_info = {'id': 1, 'name': self.repo_name, 'url': self.repo_url}

    def tearDown(self):
        mock.patch.stopall()

    def test_create_external_repo_wrong_format(self):
        repo_name = 'test-repo+'

        # name is longer as expected
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.create_external_repo(repo_name, self.repo_url)

        # not except regex rules
        self.verify_name_internal.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.create_external_repo(repo_name, self.repo_url)

    def test_create_external_repo_exists(self):
        expected = 'An external repo named "%s" already exists' % self.repo_name

        self.verify_name_internal.return_value = None
        self.get_external_repos.return_value = self.repo_info
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.create_external_repo(self.repo_name, self.repo_url)
        self.assertEqual(expected, str(cm.exception))
