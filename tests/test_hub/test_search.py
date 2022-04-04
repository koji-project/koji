import unittest

import koji
import kojihub


class TestSearch(unittest.TestCase):

    def setUp(self):
        self.exports = kojihub.RootExports()

    def test_empty_terms(self):
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.search('', 'type', 'glob')
        self.assertEqual("empty search terms", str(cm.exception))

    def test_wrong_type(self):
        type = 'test-type'
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.search('item', type, 'glob')
        self.assertEqual(f"No such search type: {type}", str(cm.exception))
