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




