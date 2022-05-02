import unittest

import koji
import kojihub


class TestGetArchiveType(unittest.TestCase):

    def test_get_archive_wrong_type_filename(self):
        filename = ['test-filename']
        with self.assertRaises(koji.ParameterError) as cm:
            kojihub.get_archive_type(filename=filename)
        self.assertEqual(f"Invalid type for value '{filename}': {type(filename)}",
                         str(cm.exception))

    def test_get_archive_without_opt(self):
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.get_archive_type()
        self.assertEqual("one of filename, type_name, or type_id must be specified",
                         str(cm.exception))
