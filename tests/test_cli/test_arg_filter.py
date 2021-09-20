import unittest

from koji_cli.lib import arg_filter

class TestArgFilter(unittest.TestCase):
    def test_valid_values(self):
        for parse_json in (True, False):
            self.assertEqual(arg_filter("1", parse_json=parse_json), 1)
            self.assertEqual(arg_filter("1.123", parse_json=parse_json), 1.123)
            self.assertEqual(arg_filter("True", parse_json=parse_json), True)
            self.assertEqual(arg_filter("False", parse_json=parse_json), False)
            self.assertEqual(arg_filter("None", parse_json=parse_json), None)

        # non/json
        self.assertEqual(arg_filter('{"a": 1}'), '{"a": 1}')
        self.assertDictEqual(arg_filter('{"a": 1}', parse_json=True), {"a": 1})

        # invalid json
        self.assertEqual(arg_filter("{'a': 1}", parse_json=True), "{'a': 1}")
