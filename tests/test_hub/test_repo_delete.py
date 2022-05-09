import unittest

import koji
import kojihub


class TestRepoDelete(unittest.TestCase):

    def test_repo_delete_wrong_type_typeID(self):
        repo_id = 'test-repo-id'
        with self.assertRaises(koji.ParameterError) as cm:
            kojihub.repo_delete(repo_id)
        self.assertEqual(f"Invalid type for value '{repo_id}': {type(repo_id)}, "
                         f"expected type <class 'int'>", str(cm.exception))
