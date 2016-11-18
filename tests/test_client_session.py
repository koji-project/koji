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
