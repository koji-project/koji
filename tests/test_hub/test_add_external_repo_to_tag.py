import unittest
from unittest import mock

import koji
import kojihub


class TestAddExternalRepoToTag(unittest.TestCase):

    def setUp(self):
        self.tag_name = 'test-tag'
        self.context = mock.patch('kojihub.kojihub.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertPerm = mock.MagicMock()
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.get_external_repo = mock.patch('kojihub.kojihub.get_external_repo').start()
        self.get_tag_external_repos = mock.patch('kojihub.kojihub.get_tag_external_repos').start()
        self.parse_arches = mock.patch('koji.parse_arches').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.tag_info = {'id': 1, 'name': self.tag_name}
        self.external_repo_info = {'id': 123, 'name': 'test-repo'}
        self.priority = 11

    def tearDown(self):
        mock.patch.stopall()

    def test_with_wrong_merge_mode(self):
        merge_mode = 'test-mode'
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.add_external_repo_to_tag(self.tag_name, 'repo', 1, merge_mode=merge_mode)
        self.assertEqual(f"No such merge mode: {merge_mode}", str(cm.exception))

    def test_priority_not_int(self):
        priority = 'test-priority'
        self.get_tag.return_value = self.tag_info
        self.get_external_repo.return_value = {'id': 123}
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.add_external_repo_to_tag(self.tag_name, 'repo', priority, merge_mode=None)
        self.assertEqual(f"Invalid type for value '{priority}': {type(priority)}, "
                         f"expected type <class 'int'>", str(cm.exception))

    def test_tag_asociated_with_ext_repo(self):
        self.get_tag.return_value = self.tag_info
        self.get_external_repo.return_value = self.external_repo_info
        self.get_tag_external_repos.return_value = [{'external_repo_id': 234},
                                                    {'external_repo_id': 123}]
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.add_external_repo_to_tag(self.tag_name, 'test-repo', self.priority)
        self.assertEqual(f"tag {self.tag_info['name']} already associated with external "
                         f"repo {self.external_repo_info['name']}", str(cm.exception))

    def test_tag_asociated_with_priority(self):
        self.get_tag.return_value = self.tag_info
        self.get_external_repo.return_value = self.external_repo_info
        self.get_tag_external_repos.return_value = [{'external_repo_id': 234, 'priority': 12},
                                                    {'external_repo_id': 345, 'priority': 11}]
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.add_external_repo_to_tag(self.tag_name, 'test-repo', self.priority)
        self.assertEqual(f"tag {self.tag_info['name']} already associated "
                         f"with an external repo at priority {self.priority}", str(cm.exception))
