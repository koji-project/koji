import unittest

import koji
import kojihub


class TestRepoSetState(unittest.TestCase):

    def test_set_state_wrong_type_typeID(self):
        repo_id = 'test-repo-id'
        with self.assertRaises(koji.ParameterError) as cm:
            kojihub.repo_set_state(repo_id, 'failed')
        self.assertEqual(f"Invalid type for value '{repo_id}': {type(repo_id)}", str(cm.exception))
