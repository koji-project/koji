import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji


class TestNewMultiCall(unittest.TestCase):

    def setUp(self):
        self._callMethod = mock.patch('koji.ClientSession._callMethod').start()
        self.session = koji.ClientSession('FAKE_URL')

    def tearDown(self):
        mock.patch.stopall()

    def test_basic_multicall(self):
        with self.session.multicall() as m:
            ret = {}
            for i in range(10):
                ret[i] = m.echo(i)
        self._callMethod.assert_called_once()
        self.assertEqual(self._callMethod.call_args[0][0], 'multiCall')
        self.assertEqual(self._callMethod.call_args[0][2], {})
        _calls = self._callMethod.call_args[0][1]
        if not isinstance(_calls, tuple) or len(_calls) != 1:
            raise Exception('multiCall args not wrapped in singleton')
        calls = _calls[0]
        for i in range(10):
            self.assertEqual(calls[i]['methodName'], "echo")
            self.assertEqual(calls[i]['params'], (i,))

    def test_batch_multicall(self):
        with self.session.multicall(batch=10) as m:
            ret = {}
            for i in range(42):
                ret[i] = m.echo(i)

        # should be 5 batches
        self.assertEqual(self._callMethod.call_count, 5)
        i = 0
        for args, kwargs in self._callMethod.call_args_list:
            self.assertEqual(kwargs, {})
            self.assertEqual(args[0], 'multiCall')
            self.assertEqual(args[2], {})
            _calls = args[1]
            if not isinstance(_calls, tuple) or len(_calls) != 1:
                raise Exception('multiCall args not wrapped in singleton')
            calls = _calls[0]
            for call in calls:
                self.assertEqual(call['methodName'], "echo")
                self.assertEqual(call['params'], (i,))
                i += 1
