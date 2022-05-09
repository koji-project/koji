import unittest
import mock

import koji
import kojihub


class TestAddExternalRepoToTag(unittest.TestCase):

    def setUp(self):
        self.tag_name = 'test-tag'
        self.get_tag = mock.patch('kojihub.get_tag').start()
        self.get_external_repo = mock.patch('kojihub.get_external_repo').start()
        self.tag_info = {'id': 1, 'name': self.tag_name}

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
