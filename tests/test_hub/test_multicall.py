import mock
import unittest

from kojihub import kojixmlrpc
from kojihub.kojixmlrpc import Fault, HandlerRegistry, ModXMLRPCRequestHandler


class DummyExports(object):

    def foo(self, bar, err=None):
        if err:
            raise err
        return bar


class TestMulticall(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.kojixmlrpc.context').start()
        self.context_db = mock.patch('kojihub.db.context').start()
        self.kojihub = mock.patch('kojihub.kojixmlrpc.kojihub').start()
        self.registry = HandlerRegistry()
        self.exports = DummyExports()
        self.registry.register_instance(self.exports)

    def tearDown(self):
        mock.patch.stopall()

    def test_multicall(self):
        kojixmlrpc.kojihub = mock.MagicMock()
        calls = [{'methodName': 'foo', 'params': [1]},
                 {'methodName': 'non', 'params': [mock.ANY]},
                 {'methodName': 'foo', 'params': [2, Exception('with int arg', 1)]},
                 {'methodName': 'foo', 'params': [3, Fault(2, 'xmlrpc fault')]}]
        h = ModXMLRPCRequestHandler(self.registry)
        h.check_session = mock.MagicMock()
        h.enforce_lockout = mock.MagicMock()
        kojixmlrpc.context.event_id = mock.MagicMock()
        rv = h.multiCall(calls)
        self.assertEqual(rv, [[1],
                              {'faultCode': 1000, 'faultString': 'Invalid method: non',
                               'traceback': mock.ANY},
                              {'faultCode': 1, 'faultString': 'with int arg, 1',
                               'traceback': mock.ANY},
                              {'faultCode': 2, 'faultString': 'xmlrpc fault'}])
        self.assertFalse(hasattr(kojixmlrpc.context, 'event_id'))
