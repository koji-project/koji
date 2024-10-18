import unittest

from unittest import mock

import kojihub

UP = kojihub.UpdateProcessor


class TestDeleteExternalRepo(unittest.TestCase):
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
        self.get_external_repo = mock.patch('kojihub.kojihub.get_external_repo').start()
        self.get_tag_external_repos = mock.patch('kojihub.kojihub.get_tag_external_repos').start()
        self.remove_external_repo_from_tag = mock.patch(
            'kojihub.kojihub.remove_external_repo_from_tag').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_valid(self):
        tag_ids = [23, 25]
        repo_id = 123
        self.context_db.event_id = 42
        self.context_db.session.user_id = 23
        self.get_external_repo.return_value = {'id': repo_id}
        self.get_tag_external_repos.return_value = [{'id': repo_id, 'tag_id': tag_ids[0]},
                                                    {'id': repo_id, 'tag_id': tag_ids[1]}]
        self.remove_external_repo_from_tag.side_effect = [None, None]
        kojihub.delete_external_repo(repo_id)

        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'external_repo_config')
        self.assertEqual(update.clauses, ['external_repo_id = %(repo_id)i', 'active = TRUE'])
        self.assertEqual(update.data, {'revoke_event': 42, 'revoker_id': 23})
        self.assertEqual(update.rawdata, {'active': 'NULL'})

        self.get_external_repo.assert_called_once_with(123, strict=True)
        self.get_tag_external_repos.assert_called_once_with(repo_info=123)
        self.remove_external_repo_from_tag.assert_has_calls(
            [mock.call(tag_info=tag_ids[0], repo_info=repo_id),
             mock.call(tag_info=tag_ids[1], repo_info=repo_id)])
