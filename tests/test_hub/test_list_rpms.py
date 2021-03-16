import unittest

import koji
import kojihub


class TestListRpms(unittest.TestCase):

    def test_wrong_type_arches(self):
        arches = {'test-arch': 'val'}
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.list_rpms(arches=arches)
        self.assertEqual('Invalid type for "arches" parameter: %s' % type(arches),
                         str(cm.exception))
