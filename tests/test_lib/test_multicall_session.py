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
        print self._callMethod.call_args
