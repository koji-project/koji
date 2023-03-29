import unittest

import mock

import kojihub


class TestGetExternalRepo(unittest.TestCase):

    def setUp(self):
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.read_full_inheritance = mock.patch('kojihub.kojihub.readFullInheritance').start()
        self.get_tag_external_repos = mock.patch('kojihub.kojihub.get_tag_external_repos').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_valid(self):
        self.get_tag.return_value = {'id': 123}
        self.read_full_inheritance.return_value = [{'parent_id': 111}, {'parent_id': 112}]
        self.get_tag_external_repos.side_effect = [
            [{'external_repo_id': 10, 'tag_id': 123}],
            [{'external_repo_id': 11, 'tag_id': 111}, {'external_repo_id': 12, 'tag_id': 111}],
            [{'external_repo_id': 13, 'tag_id': 112}]]
        result = kojihub.get_external_repo_list('test-tag')
        self.assertEqual(result, [
            {'external_repo_id': 10, 'tag_id': 123},
            {'external_repo_id': 11, 'tag_id': 111}, {'external_repo_id': 12, 'tag_id': 111},
            {'external_repo_id': 13, 'tag_id': 112}])
        self.get_tag.assert_called_once_with('test-tag', strict=True, event=None)
        self.read_full_inheritance.assert_called_once_with(123, None)
        self.get_tag_external_repos.assert_has_calls(
            [mock.call(tag_info=123, event=None), mock.call(tag_info=111, event=None),
             mock.call(tag_info=112, event=None)])
