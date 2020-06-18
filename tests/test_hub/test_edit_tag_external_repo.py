import mock
import unittest

import koji
import kojihub


class TestEditTagExternalRepo(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.get_tag = mock.patch('kojihub.get_tag').start()
        self.get_external_repo = mock.patch('kojihub.get_external_repo').start()
        self.get_tag_external_repos = mock.patch('kojihub.get_tag_external_repos').start()
        self.get_tag.return_value = {'id': 1, 'name': 'tag'}
        self.get_external_repo.return_value = {'id': 11, 'name': 'ext_repo'}
        self.get_tag_external_repos.return_value = [{'external_repo_id': 11,
                                                     'tag_id': 1,
                                                     'priority': 5,
                                                     'merge_mode': 'simple'}]

        self.remove_external_repo_from_tag = mock.patch(
            'kojihub.remove_external_repo_from_tag').start()
        self.add_external_repo_to_tag = mock.patch('kojihub.add_external_repo_to_tag').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_edit(self):
        rv = kojihub.edit_tag_external_repo('tag', 'ext_repo', priority=6, merge_mode='bare')
        self.get_tag.assert_called_once_with('tag', strict=True)
        self.get_external_repo.assert_called_once_with('ext_repo', strict=True)
        self.get_tag_external_repos.assert_called_once_with(tag_info=1, repo_info=11)
        self.remove_external_repo_from_tag.assert_called_once_with(1, 11)
        self.add_external_repo_to_tag.assert_called_once_with(1, 11, priority=6, merge_mode='bare')
        self.assertTrue(rv)

    def test_edit_no_tag_repo(self):
        self.get_tag_external_repos.return_value = []
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.edit_tag_external_repo('tag', 'ext_repo', priority=6, merge_mode='bare')
        self.assertEqual(cm.exception.args[0],
                         'external repo ext_repo not associated with tag tag')
        self.get_tag.assert_called_once_with('tag', strict=True)
        self.get_external_repo.assert_called_once_with('ext_repo', strict=True)
        self.get_tag_external_repos.assert_called_once_with(tag_info=1, repo_info=11)
        self.remove_external_repo_from_tag.assert_not_called()
        self.add_external_repo_to_tag.assert_not_called()

    def test_edit_no_changes_2(self):
        rv = kojihub.edit_tag_external_repo('tag', 'ext_repo', priority=5, merge_mode='simple')
        self.remove_external_repo_from_tag.assert_not_called()
        self.add_external_repo_to_tag.assert_not_called()
        self.assertFalse(rv)

    def test_edit_all_none(self):
        self.get_tag_external_repos.return_value = [{'external_repo_id': 11,
                                                     'tag_id': 1,
                                                     'priority': None,
                                                     'merge_mode': None}]
        rv = kojihub.edit_tag_external_repo('tag', 'ext_repo', priority=None, merge_mode=None)
        self.remove_external_repo_from_tag.assert_not_called()
        self.add_external_repo_to_tag.assert_not_called()
        self.assertFalse(rv)

    def test_edit_none_new(self):
        rv = kojihub.edit_tag_external_repo('tag', 'ext_repo', priority=None, merge_mode=None)
        self.remove_external_repo_from_tag.assert_not_called()
        self.add_external_repo_to_tag.assert_not_called()
        self.assertFalse(rv)

    def test_edit_none_old(self):
        self.get_tag_external_repos.return_value = [{'external_repo_id': 11,
                                                     'tag_id': 1,
                                                     'priority': 5,
                                                     'merge_mode': None}]
        rv = kojihub.edit_tag_external_repo('tag', 'ext_repo', priority=None, merge_mode='simple')
        self.remove_external_repo_from_tag.assert_called_once_with(1, 11)
        self.add_external_repo_to_tag.assert_called_once_with(1, 11,
                                                              priority=5, merge_mode='simple')
        self.assertTrue(rv)
