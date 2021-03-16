import unittest

import koji
import kojihub


class TestGetLastEvent(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()

    def test_wrong_type_before(self):
        before = '12345'
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getLastEvent(before)
        self.assertEqual("Invalid type for before: %s" % type(before), str(cm.exception))
