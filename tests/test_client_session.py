import mock
import unittest

import koji


class TestClientSession(unittest.TestCase):

    @mock.patch('socket.getfqdn')
    def test_server_principal_rdns(self, getfqdn):
        opts = {'krb_rdns': True}
        session = koji.ClientSession('http://koji.example.com/kojihub', opts)
        cprinc = mock.MagicMock()
        cprinc.realm = "REALM"
        getfqdn.return_value = 'koji02.example.com'

        princ = session._serverPrincipal(cprinc)
        self.assertEqual(princ, 'host/koji02.example.com@REALM')
        getfqdn.assert_called_with('koji.example.com')

    @mock.patch('socket.getfqdn')
    def test_server_principal_no_rdns(self, getfqdn):
        opts = {'krb_rdns': False}
        session = koji.ClientSession('http://koji.example.com/kojihub', opts)
        cprinc = mock.MagicMock()
        cprinc.realm = "REALM"
        getfqdn.return_value = 'koji02.example.com'

        princ = session._serverPrincipal(cprinc)
        self.assertEqual(princ, 'host/koji.example.com@REALM')
        getfqdn.assert_not_called()

    @mock.patch('koji.compatrequests.Session')
    @mock.patch('requests.Session')
    def test_new_session(self, rsession, compat_session):
        opts = {'use_old_ssl': False}
        ksession = koji.ClientSession('http://koji.example.com/kojihub', opts)

        # init should have called new_session for us

        rsession.assert_called_once()
        compat_session.assert_not_called()

    @mock.patch('koji.compatrequests.Session')
    @mock.patch('requests.Session')
    def test_new_session_old(self, rsession, compat_session):
        opts = {'use_old_ssl': True}
        ksession = koji.ClientSession('http://koji.example.com/kojihub', opts)

        # init should have called new_session for us

        rsession.assert_not_called()
        compat_session.assert_called_once()

    @mock.patch('koji.compatrequests.Session')
    @mock.patch('requests.Session')
    def test_new_session_close(self, rsession, compat_session):
        opts = {'use_old_ssl': True}
        ksession = koji.ClientSession('http://koji.example.com/kojihub', opts)
        my_rsession = mock.MagicMock()
        ksession.rsession = my_rsession

        ksession.new_session()
        my_rsession.close.assert_called()
        self.assertNotEqual(ksession.rsession, my_rsession)

class TestFastUpload(unittest.TestCase):
    @mock.patch('koji.compatrequests.Session')
    @mock.patch('requests.Session')
    @mock.patch('__builtin__.file')
    @mock.patch('os.path.getsize')
    def test_fastUpload(self, getsize_mock, file_mock, rsession, compat_session):
        ksession = koji.ClientSession('http://koji.example.com/kojihub', {})

        # without login (ActionNotAllowed)
        ksession.logged_in = False
        with self.assertRaises(koji.ActionNotAllowed):
            ksession.fastUpload('nonexistent_file', 'target')

        # fake login
        ksession.logged_in = True
        ksession.sinfo = {}
        ksession.callnum = 1
        ksession._callMethod = mock.MagicMock()

        # fail with nonexistent file (IOError)
        file_mock.side_effect = IOError('mocked exception')
        with self.assertRaises(IOError):
            ksession.fastUpload('file', 'target')

        # inaccessible file, permissions (IOError)
        file_mock.side_effect = IOError('mocked exception')
        with self.assertRaises(IOError):
            ksession.fastUpload('file', 'target')

        # upload empty file (success)
        file_mock.side_effect = None
        fileobj = mock.MagicMock()
        fileobj.read.return_value = ''
        file_mock.return_value = fileobj
        ksession._callMethod.return_value = {
            'size': 0,
            'hexdigest': koji.util.adler32_constructor().hexdigest()
        }
        ksession.fastUpload('file', 'target')

        # upload regular file (success)
        file_mock.side_effect = None
        fileobj = mock.MagicMock()
        fileobj.read.side_effect = ['123123', '']
        file_mock.return_value = fileobj
        ksession._callMethod.reset_mock()
        ksession._callMethod.side_effect = [
            {'size': 6, 'hexdigest': '041c012d'}, # rawUpload
            {'size': 6, 'hexdigest': '041c012d'}, # checkUpload
        ]
        ksession.fastUpload('file', 'target', blocksize=1024)

        # change file size during upload (success)
        file_mock.side_effect = None
        fileobj = mock.MagicMock()
        fileobj.read.side_effect = ['123123', '']
        file_mock.return_value = fileobj
        getsize_mock.return_value = 123456
        ksession._callMethod.reset_mock()
        ksession._callMethod.side_effect = [
            {'size': 6, 'hexdigest': '041c012d'}, # rawUpload
            {'size': 6, 'hexdigest': '041c012d'}, # checkUpload
        ]
        ksession.fastUpload('file', 'target', blocksize=1024)

        # uploaded file is corrupted (length) (GenericError)
        file_mock.side_effect = None
        fileobj = mock.MagicMock()
        fileobj.read.side_effect = ['123123', '']
        file_mock.return_value = fileobj
        getsize_mock.return_value = 123456
        ksession._callMethod.reset_mock()
        ksession._callMethod.side_effect = [
            {'size': 6, 'hexdigest': '041c012d'}, # rawUpload
            {'size': 3, 'hexdigest': '041c012d'}, # checkUpload
        ]
        with self.assertRaises(koji.GenericError):
            ksession.fastUpload('file', 'target', blocksize=1024)

        # uploaded file is corrupted (checksum) (GenericError)
        file_mock.side_effect = None
        fileobj = mock.MagicMock()
        fileobj.read.side_effect = ['123123', '']
        file_mock.return_value = fileobj
        getsize_mock.return_value = 123456
        ksession._callMethod.reset_mock()
        ksession._callMethod.side_effect = [
            {'size': 6, 'hexdigest': '041c012d'}, # rawUpload
            {'size': 3, 'hexdigest': 'deadbeef'}, # checkUpload
        ]
        with self.assertRaises(koji.GenericError):
            ksession.fastUpload('file', 'target', blocksize=1024)
