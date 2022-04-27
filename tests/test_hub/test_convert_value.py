import unittest

import koji
from kojihub import convert_value


class TestConvertValue(unittest.TestCase):
    def test_convert_ok(self):
        cases = (
            (str, 'text'),
            (int, 1),
            (bool, True)
        )
        for cast, input in cases:
            output = convert_value(input, cast=cast)
            self.assertEqual(input, output)

    def test_convert_fail(self):
        with self.assertRaises(koji.ParameterError):
            convert_value('asd', cast=int)

    def test_convert_exc(self):
        with self.assertRaises(IOError):
            convert_value('asd', cast=int, exc_type=IOError)

    def test_none(self):
        with self.assertRaises(koji.ParameterError):
            convert_value(None, cast=int)
        value = convert_value(None, cast=int, none_allowed=True)
        self.assertIsNone(value)

    def test_message(self):
        msg = 'test_message'
        with self.assertRaises(koji.ParameterError) as ex:
            convert_value(None, cast=int, message=msg)
        self.assertEqual(str(ex.exception), msg)

    def test_only(self):
        "fail on otherwise valid conversions"
        with self.assertRaises(koji.ParameterError):
            convert_value(None, cast=bool, check_only=True)

