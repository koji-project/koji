from __future__ import absolute_import
import mock
import six
import weakref
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji
from koji.xmlrpcplus import Fault


class TestClientSession(unittest.TestCase):
    @mock.patch('requests.Session')
    def test_new_session(self, rsession):
        koji.ClientSession('http://koji.example.com/kojihub')

        # init should have called new_session for us

        rsession.assert_called_once()

    @mock.patch('requests.Session')
    def test_new_session_close(self, rsession):
        if six.PY3:
            return
        ksession = koji.ClientSession('http://koji.example.com/kojihub')
        my_rsession = mock.MagicMock()
        ksession.rsession = my_rsession

        ksession.new_session()
        my_rsession.close.assert_called()
        self.assertNotEqual(ksession.rsession, my_rsession)


class TestFastUpload(unittest.TestCase):

    def setUp(self):
        self.ksession = koji.ClientSession('http://koji.example.com/kojihub')
        self.ksession.logout = mock.MagicMock()
        self.do_fake_login()
        # mocks
        self.ksession._callMethod = mock.MagicMock()
        self.ksession.retries = 1
        self.rsession = mock.patch('requests.Session').start()
        if six.PY2:
            self.file_mock = mock.patch('__builtin__.open').start()
        else:
            self.file_mock = mock.patch('builtins.open').start()
        self.getsize_mock = mock.patch('os.path.getsize').start()

    def tearDown(self):
        del self.ksession
        mock.patch.stopall()

    def do_fake_login(self):
        self.ksession.logged_in = True
        self.ksession.sinfo = {}
        self.ksession.callnum = 1

    def test_fastUpload_nologin(self):
        # without login (ActionNotAllowed)
        self.ksession.logged_in = False
        with self.assertRaises(koji.ActionNotAllowed):
            self.ksession.fastUpload('nonexistent_file', 'target')

    def test_fastUpload_nofile(self):
        # fail with nonexistent file (IOError)
        self.file_mock.side_effect = IOError('mocked exception')
        with self.assertRaises(IOError):
            self.ksession.fastUpload('file', 'target')

    def test_fastUpload_empty_file(self):
        # upload empty file (success)
        fileobj = mock.MagicMock()
        fileobj.read.return_value = ''
        self.file_mock.return_value = fileobj
        self.ksession._callMethod.return_value = {
            'size': 0,
            'hexdigest': koji.util.adler32_constructor().hexdigest()
        }
        self.ksession.fastUpload('file', 'target')

    def test_fastUpload_regular_file(self):
        # upload regular file (success)
        fileobj = mock.MagicMock()
        fileobj.read.side_effect = ['123123', '']
        self.file_mock.return_value = fileobj
        self.ksession._callMethod.side_effect = [
            {'size': 6, 'hexdigest': '041c012d'}, # rawUpload
            {'size': 6, 'hexdigest': '041c012d'}, # checkUpload
        ]
        self.ksession.fastUpload('file', 'target', blocksize=1024)

    def test_fastUpload_size_change(self):
        # change file size during upload (success)
        fileobj = mock.MagicMock()
        fileobj.read.side_effect = ['123123', '']
        self.file_mock.return_value = fileobj
        self.getsize_mock.return_value = 123456
        self.ksession._callMethod.side_effect = [
            {'size': 6, 'hexdigest': '041c012d'}, # rawUpload
            {'size': 6, 'hexdigest': '041c012d'}, # checkUpload
        ]
        self.ksession.fastUpload('file', 'target', blocksize=1024)

    def test_fastUpload_wrong_length(self):
        # uploaded file is corrupted (length) (GenericError)
        fileobj = mock.MagicMock()
        fileobj.read.side_effect = ['123123', '']
        self.file_mock.return_value = fileobj
        self.getsize_mock.return_value = 123456
        self.ksession._callMethod.side_effect = [
            {'size': 6, 'hexdigest': '041c012d'}, # rawUpload
            {'size': 3, 'hexdigest': '041c012d'}, # checkUpload
        ]
        with self.assertRaises(koji.GenericError):
            self.ksession.fastUpload('file', 'target', blocksize=1024)

    def test_fastUpload_wrong_checksum(self):
        # uploaded file is corrupted (checksum) (GenericError)
        fileobj = mock.MagicMock()
        fileobj.read.side_effect = ['123123', '']
        self.file_mock.return_value = fileobj
        self.getsize_mock.return_value = 123456
        self.ksession._callMethod.side_effect = [
            {'size': 6, 'hexdigest': '041c012d'}, # rawUpload
            {'size': 3, 'hexdigest': 'deadbeef'}, # checkUpload
        ]
        with self.assertRaises(koji.GenericError):
            self.ksession.fastUpload('file', 'target', blocksize=1024)

    def test_fastUpload_nondefault_volume(self):
        # upload regular file (success)
        fileobj = mock.MagicMock()
        fileobj.read.side_effect = ['123123', '']
        self.file_mock.return_value = fileobj
        self.ksession._callMethod.side_effect = [
            {'size': 6, 'hexdigest': '041c012d'}, # rawUpload
            {'size': 6, 'hexdigest': '041c012d'}, # checkUpload
        ]
        self.ksession.fastUpload('file', 'target', blocksize=1024, volume='foobar')
        for call in self.ksession._callMethod.call_args_list:
            # both calls should pass volume as a named arg to the method
            # (note: not literally a named arg to _callMethod)
            # _callMethod args are: method, method_args, method_kwargs
            kwargs = call[0][2]
            self.assertTrue('volume' in kwargs)
            self.assertEqual(kwargs['volume'], 'foobar')


class TestMultiCall(unittest.TestCase):

    def setUp(self):
        self.ksession = koji.ClientSession('http://koji.example.com/kojihub')
        # mocks
        self.ksession._sendCall = mock.MagicMock()
        self.ksession.logout = mock.MagicMock()

    def tearDown(self):
        del self.ksession

    def test_multiCall_disable(self):
        with self.assertRaises(koji.GenericError) as cm:
            self.ksession.multiCall()
        self.assertEqual(cm.exception.args[0],
                         "ClientSession.multicall must be set to True"
                         " before calling multiCall()")

    def test_multiCall_empty(self):
        self.ksession.multicall = True
        ret = self.ksession.multiCall()
        self.assertEqual([], ret)
        self.ksession._sendCall.assert_not_called()

    def test_multiCall_strict(self):
        self.ksession._sendCall.return_value = [[], {'faultCode': 1000,
                                               'faultString': 'msg'}]
        self.ksession.multicall = True
        self.ksession.methodA('a', 'b', c='c')
        self.ksession.methodB(1, 2, 3)
        with self.assertRaises(koji.GenericError):
            self.ksession.multiCall(strict=True)

    def test_multiCall_not_strict(self):
        self.ksession._sendCall.return_value = [[], {'faultCode': 1000,
                                                     'faultString': 'msg'}]
        self.ksession.multicall = True
        self.ksession.methodA('a', 'b', c='c')
        self.ksession.methodB(1, 2, 3)
        ret = self.ksession.multiCall()
        self.assertFalse(self.ksession.multicall)
        self.assertEqual([[], {'faultCode': 1000, 'faultString': 'msg'}], ret)

    def test_multiCall_batch(self):
        self.ksession._sendCall.side_effect = [[['a', 'b', 'c']],
                                               [{'faultCode': 1000,
                                                 'faultString': 'msg'}]]
        self.ksession.multicall = True
        self.ksession.methodA('a', 'b', c='c')
        self.ksession.methodB(1, 2, 3)
        ret = self.ksession.multiCall(batch=1)
        self.assertFalse(self.ksession.multicall)
        self.assertEqual(2, self.ksession._sendCall.call_count)
        self.assertEqual([['a', 'b', 'c'],
                          {'faultCode': 1000, 'faultString': 'msg'}], ret)

    def test_MultiCallHack_weakref_validation(self):
        expected_exc = 'The session parameter must be a weak reference'
        with self.assertRaisesRegexp(TypeError, expected_exc):
            koji.MultiCallHack(self.ksession)

        # This should not raise an exception
        koji.MultiCallHack(weakref.ref(self.ksession))
