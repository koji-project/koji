import unittest

import koji
import kojihub


class TestAddExternalRepoToTag(unittest.TestCase):

    def test_with_wrong_merge_mode(self):
        merge_mode = 'test-mode'
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.add_external_repo_to_tag('tag', 'repo', 1, merge_mode=merge_mode)
        self.assertEqual('No such merge mode: %s' % merge_mode, str(cm.exception))
