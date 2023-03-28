import unittest
import mock

import koji
import kojihub

UP = kojihub.UpdateProcessor


class TestRemoveExternalRepoFromTag(unittest.TestCase):
    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.context_db = mock.patch('kojihub.db.context').start()
        self.context_db.session.assertLogin = mock.MagicMock()
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.get_tag_external_repos = mock.patch('kojihub.kojihub.get_tag_external_repos').start()
        self.get_external_repo = mock.patch('kojihub.kojihub.get_external_repo').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_not_exist_tag_external_repo(self):
        tag_info = {'id': 22, 'name': 'test-tag'}
        repo_info = {'id': 1, 'name': 'test-repo'}
        self.get_tag.return_value = tag_info
        self.get_external_repo.return_value = repo_info
        self.get_tag_external_repos.return_value = None
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.remove_external_repo_from_tag(tag_info['name'], repo_info['name'])
        self.assertEqual(
            f'external repo {repo_info["name"]} not associated with tag {tag_info["name"]}',
            str(ex.exception))

        self.assertEqual(len(self.updates), 0)
        self.get_tag.assert_called_once_with(tag_info['name'], strict=True)
        self.get_external_repo.assert_called_once_with(repo_info['name'], strict=True)
        self.get_tag_external_repos.assert_called_once_with(
            tag_info=tag_info['id'], repo_info=repo_info['id'])

    def test_valid(self):
        tag_info = {'id': 22, 'name': 'test-tag'}
        repo_info = {'id': 1, 'name': 'test-repo'}
        self.context_db.event_id = 42
        self.context_db.session.user_id = 23
        self.get_tag.return_value = tag_info
        self.get_external_repo.return_value = repo_info
        self.get_tag_external_repos.return_value = [{'id': repo_info['id'],
                                                     'tag_id': tag_info['id']}]
        kojihub.remove_external_repo_from_tag(tag_info['name'], repo_info['name'])

        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'tag_external_repos')
        self.assertEqual(update.clauses, ["tag_id = %(tag_id)i", "external_repo_id = %(repo_id)i",
                                          'active = TRUE'])
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 23})
        self.assertEqual(update.rawdata, {'active': 'NULL'})

        self.get_tag.assert_called_once_with(tag_info['name'], strict=True)
        self.get_external_repo.assert_called_once_with(repo_info['name'], strict=True)
        self.get_tag_external_repos.assert_called_once_with(
            tag_info=tag_info['id'], repo_info=repo_info['id'])
