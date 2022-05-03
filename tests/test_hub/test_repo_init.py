import unittest

import koji
import kojihub


class TestRepoInit(unittest.TestCase):

    def test_repo_init_wrong_type_typeID(self):
        task_id = 'test-task_id'
        with self.assertRaises(koji.ParameterError) as cm:
            kojihub.repo_init('test-tag', task_id)
        self.assertEqual(f"Invalid type for value '{task_id}': {type(task_id)}, "
                         f"expected type <class 'int'>", str(cm.exception))
