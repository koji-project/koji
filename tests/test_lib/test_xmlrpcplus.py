import unittest

import xmlrpclib
from koji import xmlrpcplus


class TestDump(unittest.TestCase):

    standard_data = [
            "Hello World",
            5,
            5.5,
            None,
            True,
            False,
            [1],
            {"a": 1},
            ["fnord"],
            {"a": ["b", 1, 2, None], "b": {"c": 1}},
        ]

    def test_standard_data(self):
        for value in self.standard_data:
            value = (value,)
            enc = xmlrpcplus.dumps(value)
            _enc = xmlrpclib.dumps(value, allow_none=1)
            self.assertEqual(enc, _enc)
            params, method = xmlrpclib.loads(enc)
            self.assertEqual(params, value)
            self.assertEqual(method, None)

    def gendata(self):
        for value in self.standard_data:
            yield value

    def test_generator(self):
        value = (self.gendata(),)
        enc = xmlrpcplus.dumps(value)
        params, method = xmlrpclib.loads(enc)
        expect = (list(self.gendata()),)
        self.assertEqual(params, expect)
        self.assertEqual(method, None)

    long_data = [
            2 ** 63,
            -(2 ** 63),
            [2**n - 1 for n  in range(65)],
            {"a": [2 ** 63, 5], "b": 2**63+42},
            ]

    def test_i8(self):
        for value in self.long_data:
            value = (value,)
            enc = xmlrpcplus.dumps(value)
            params, method = xmlrpclib.loads(enc)
            self.assertEqual(params, value)
            self.assertEqual(method, None)

    def test_overflow(self):
        value = (2**64,)
        with self.assertRaises(OverflowError):
            xmlrpcplus.dumps(value)
