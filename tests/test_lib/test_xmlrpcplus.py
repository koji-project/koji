# coding=utf-8
from __future__ import absolute_import
from six.moves import range
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from six.moves import xmlrpc_client
from koji import xmlrpcplus


class TestDump(unittest.TestCase):

    standard_data = [
            "Hello World",
            5,
            5.5,
            None,
            True,
            False,
            u'Hævē s°mə ŭnıčođė',
            [1],
            {"a": 1},
            ["fnord"],
            {"a": ["b", 1, 2, None], "b": {"c": 1}},
        ]

    def test_call(self):
        method = 'my_rpc_method'
        for value in self.standard_data:
            value = (value, "other arg")
            enc = xmlrpcplus.dumps(value, methodname=method)
            _enc = xmlrpc_client.dumps(value, methodname=method, allow_none=1)
            self.assertEqual(enc, _enc)
            params, method = xmlrpc_client.loads(enc)
            self.assertEqual(params, value)
            self.assertEqual(method, method)

    def test_response(self):
        for value in self.standard_data:
            value = (value,)
            enc = xmlrpcplus.dumps(value, methodresponse=1)
            _enc = xmlrpc_client.dumps(value, methodresponse=1, allow_none=1)
            self.assertEqual(enc, _enc)
            params, method = xmlrpc_client.loads(enc)
            self.assertEqual(params, value)
            self.assertEqual(method, None)

    def test_just_data(self):
        # xmlrpc_client supports this case, so I guess we should too
        # neither method call nor response
        for value in self.standard_data:
            value = (value, "foo", "bar")
            enc = xmlrpcplus.dumps(value)
            _enc = xmlrpc_client.dumps(value, allow_none=1)
            self.assertEqual(enc, _enc)
            params, method = xmlrpc_client.loads(enc)
            self.assertEqual(params, value)
            self.assertEqual(method, None)

    def gendata(self):
        for value in self.standard_data:
            yield value

    def test_generator(self):
        value = (self.gendata(),)
        enc = xmlrpcplus.dumps(value, methodresponse=1)
        params, method = xmlrpc_client.loads(enc)
        expect = (list(self.gendata()),)
        self.assertEqual(params, expect)
        self.assertEqual(method, None)

    long_data = [
            2 ** 63 - 1,
            -(2 ** 63),
            [2**n - 1 for n  in range(64)],
            {"a": [2 ** 63 - 23, 5], "b": 2**63 - 42},
            ]

    def test_i8(self):
        for value in self.long_data:
            value = (value,)
            enc = xmlrpcplus.dumps(value, methodresponse=1)
            params, method = xmlrpc_client.loads(enc)
            self.assertEqual(params, value)
            self.assertEqual(method, None)
        # and as a call
        method = "foomethod"
        value = tuple(self.long_data)
        enc = xmlrpcplus.dumps(value, methodname=method)
        params, method = xmlrpc_client.loads(enc)
        self.assertEqual(params, value)
        self.assertEqual(method, method)

    def test_overflow(self):
        value = (2**64,)
        with self.assertRaises(OverflowError):
            xmlrpcplus.dumps(value)

    def test_fault(self):
        code = 1001
        msg = "some useless error"
        f1 = xmlrpcplus.Fault(code, msg)
        f2 = xmlrpc_client.Fault(code, msg)
        value = f1
        enc = xmlrpcplus.dumps(value, methodresponse=1)
        _enc = xmlrpc_client.dumps(value, methodresponse=1, allow_none=1)
        self.assertEqual(enc, _enc)
        try:
            params, method = xmlrpc_client.loads(enc)
        except xmlrpc_client.Fault as e:
            self.assertEqual(e.faultCode, code)
            self.assertEqual(e.faultString, msg)
        else:
            raise Exception('Fault not raised')

    def test_badargs(self):
        wrong_type = ["a", 0, 0.1, [], {}, True]
        for value in wrong_type:
            with self.assertRaises(TypeError):
                xmlrpcplus.dumps(value, methodname="foo")
        # responses much be singletons
        value = (1, 2, 3)
        with self.assertRaises(ValueError):
            xmlrpcplus.dumps(value, methodresponse=1)

    def test_marshaller(self):
        value = 3.14159
        value = (value,)
        enc = xmlrpcplus.dumps(value, methodresponse=1, marshaller=MyMarshaller)
        params, method = xmlrpc_client.loads(enc)
        # MyMarshaller rounds off floats
        self.assertEqual(params, (3,))
        self.assertEqual(method, None)

    def test_encoding(self):
        data = [
                45,
                ["hello", "world"],
                {"a": 5.5, "b": [None]},
                ]
        for value in data:
            value = (value,)
            enc = xmlrpcplus.dumps(value, methodresponse=1, encoding='us-ascii')
            _enc = xmlrpc_client.dumps(value, methodresponse=1, allow_none=1, encoding='us-ascii')
            self.assertEqual(enc, _enc)
            params, method = xmlrpc_client.loads(enc)
            self.assertEqual(params, value)
            self.assertEqual(method, None)

    def test_no_i8(self):
        # we shouldn't use i8 if we don't have to
        data = [
                23,
                42,
                -1024,
                2 ** 31 - 1,
                -2 ** 31,
                [2**31 -1],
                {"a": -2 ** 31, "b": 3.14},
                ]
        for value in data:
            value = (value,)
            enc = xmlrpcplus.dumps(value, methodresponse=1, encoding='us-ascii')
            _enc = xmlrpc_client.dumps(value, methodresponse=1, allow_none=1, encoding='us-ascii')
            if 'i8' in enc or 'I8' in enc:
                raise Exception('i8 used unnecessarily')
            self.assertEqual(enc, _enc)
            params, method = xmlrpc_client.loads(enc)
            self.assertEqual(params, value)
            self.assertEqual(method, None)


class MyMarshaller(xmlrpcplus.ExtendedMarshaller):

    dispatch = xmlrpcplus.ExtendedMarshaller.dispatch.copy()

    def dump_float_rounded(self, value, write):
        value = int(value)
        self.dump_int(value, write)

    dispatch[float] = dump_float_rounded
