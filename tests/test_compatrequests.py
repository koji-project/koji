from __future__ import absolute_import
import six.moves.http_client
import mock
import unittest
import urlparse

import koji.compatrequests


class TestResponse(unittest.TestCase):

    def setUp(self):
        session = mock.MagicMock()
        response = mock.MagicMock()
        self.response = koji.compatrequests.Response(session, response)

    def tearDown(self):
        del self.response

    def test_read(self):
        self.response.response.status = 200
        data = [
            "Here's some data",
            "Here's some mooore data",
            "And look!",
            "Here's a nice block of lorem text",
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do "
            "eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut "
            "enim ad minim veniam, quis nostrud exercitation ullamco laboris "
            "nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor "
            "in reprehenderit in voluptate velit esse cillum dolore eu fugiat "
            "nulla pariatur. Excepteur sint occaecat cupidatat non proident, "
            "sunt in culpa qui officia deserunt mollit anim id est laborum.",
            "",  #eof
        ]
        self.response.response.read.side_effect = data

        result = list(self.response.iter_content(blocksize=10240))

        self.assertEqual(result, data[:-1])
        rcalls = [mock.call(10240) for s in data]
        self.response.response.read.assert_has_calls(rcalls)

        self.response.close()
        self.response.response.close.assert_called_once()

    def test_error(self):
        self.response.response.status = 404
        self.response.response.getheader.return_value = 0
        with self.assertRaises(Exception):
            list(self.response.iter_content(8192))
        self.response.response.read.assert_not_called()

        self.response.response.status = 404
        self.response.response.getheader.return_value = 42
        with self.assertRaises(Exception):
            list(self.response.iter_content(8192))
        self.response.response.read.assert_called_once()

        self.response.response.status = 404
        self.response.response.reason = 'Not Found'
        self.response.response.getheader.return_value = 42
        with self.assertRaises(six.moves.http_client.HTTPException):
            self.response.raise_for_status()



class TestSessionPost(unittest.TestCase):

    def test_simple(self):
        session = koji.compatrequests.Session()
        url = 'https://www.fakedomain.org/KOJIHUB'
        cnx = mock.MagicMock()
        session.get_connection = mock.MagicMock()
        session.get_connection.return_value = cnx
        response = mock.MagicMock()
        cnx.getresponse.return_value = response

        ret  = session.post(url, data="data", headers={"foo": "bar"})
        cnx.putrequest.assert_called_once_with('POST', '/KOJIHUB')
        cnx.putheader.assert_called_once_with('foo', 'bar')
        cnx.send.assert_called_once_with("data")
        self.assertEqual(ret.response, response)

    def test_less_simple(self):
        session = koji.compatrequests.Session()
        url = 'https://www.fakedomain.org/KOJIHUB?a=1&b=2'
        cnx = mock.MagicMock()
        session.get_connection = mock.MagicMock()
        session.get_connection.return_value = cnx
        response = mock.MagicMock()
        cnx.getresponse.return_value = response

        ret  = session.post(url, data="data", headers={"foo": "bar"},
                cert="cert", verify="verify", stream=True, timeout=1701)
        cnx.putrequest.assert_called_once_with('POST', '/KOJIHUB?a=1&b=2')
        cnx.putheader.assert_called_once_with('foo', 'bar')
        cnx.send.assert_called_once_with("data")
        self.assertEqual(ret.response, response)


class TestSessionConnection(unittest.TestCase):

    @mock.patch('httplib.HTTPConnection')
    def test_http(self, HTTPConnection):
        # no cert, no verify, no timeout
        session = koji.compatrequests.Session()
        url = 'http://www.fakedomain234234.org/KOJIHUB?a=1&b=2'
        uri = urlparse.urlsplit(url)

        cnx = session.get_connection(uri, None, None, None)
        HTTPConnection.assert_called_once_with('www.fakedomain234234.org', 80)
        key = ('http', 'www.fakedomain234234.org', None, None, None)
        self.assertEqual(session.connection, (key, cnx))

        # and close it
        session.close()
        self.assertEqual(session.connection, None)
        cnx.close.assert_called_with()

        # double close should not error
        session.close()

    def test_cached(self):
        session = koji.compatrequests.Session()
        url = 'http://www.fakedomain234234.org/KOJIHUB?a=1&b=2'
        uri = urlparse.urlsplit(url)
        key = ('http', 'www.fakedomain234234.org', None, None, None)
        cnx = mock.MagicMock()
        session.connection = (key, cnx)

        ret = session.get_connection(uri, None, None, None)
        self.assertEqual(ret, cnx)

    def test_badproto(self):
        session = koji.compatrequests.Session()
        url = 'nosuchproto://www.fakedomain234234.org/KOJIHUB?a=1&b=2'
        uri = urlparse.urlsplit(url)

        with self.assertRaises(IOError):
            ret = session.get_connection(uri, None, None, None)

    @mock.patch('httplib.HTTPConnection')
    @mock.patch('sys.version_info', new=(2, 7, 12, 'final', 0))
    def test_timeout(self, HTTPConnection):
        # no cert, no verify
        session = koji.compatrequests.Session()
        url = 'http://www.fakedomain234234.org/KOJIHUB?a=1&b=2'
        uri = urlparse.urlsplit(url)
        timeout = 1701

        cnx = session.get_connection(uri, None, None, 1701)
        HTTPConnection.assert_called_once_with('www.fakedomain234234.org', 80, timeout=1701)
        key = ('http', 'www.fakedomain234234.org', None, None, 1701)
        self.assertEqual(session.connection, (key, cnx))

    @mock.patch('httplib.HTTPConnection')
    @mock.patch('sys.version_info', new=(2, 4, 3, 'final', 0))
    def test_timeout_compat(self, HTTPConnection):
        # no cert, no verify
        session = koji.compatrequests.Session()
        url = 'http://www.fakedomain234234.org/KOJIHUB?a=1&b=2'
        uri = urlparse.urlsplit(url)
        timeout = 1701

        cnx = session.get_connection(uri, None, None, 1701)
        HTTPConnection.assert_called_once_with('www.fakedomain234234.org', 80)
        key = ('http', 'www.fakedomain234234.org', None, None, 1701)
        self.assertEqual(session.connection, (key, cnx))
        cnx.connect.assert_called_once()
        cnx.sock.settimeout.assert_called_with(1701)

    @mock.patch('httplib.HTTPSConnection')
    def test_https(self, HTTPSConnection):
        # no cert, no verify, no timeout
        session = koji.compatrequests.Session()
        url = 'https://www.fakedomain234234.org/KOJIHUB?a=1&b=2'
        uri = urlparse.urlsplit(url)

        cnx = session.get_connection(uri, None, None, None)
        HTTPSConnection.assert_called_once_with('www.fakedomain234234.org', 443)
        key = ('https', 'www.fakedomain234234.org', None, None, None)
        self.assertEqual(session.connection, (key, cnx))

    @mock.patch('koji.ssl.SSLCommon.CreateSSLContext')
    @mock.patch('koji.ssl.SSLCommon.PlgHTTPSConnection')
    def test_cert(self, PlgHTTPSConnection, CreateSSLContext):
        # no verify, no timeout
        session = koji.compatrequests.Session()
        url = 'https://www.fakedomain234234.org/KOJIHUB?a=1&b=2'
        uri = urlparse.urlsplit(url)
        cert = '/path/to/cert/file'
        context = mock.MagicMock()
        CreateSSLContext.return_value = context

        cnx = session.get_connection(uri, cert, None, None)
        PlgHTTPSConnection.assert_called_once_with('www.fakedomain234234.org', 443, ssl_context=context)
        key = ('https', 'www.fakedomain234234.org', cert, None, None)
        self.assertEqual(session.connection, (key, cnx))

    @mock.patch('ssl._create_unverified_context')
    @mock.patch('httplib.HTTPSConnection')
    @mock.patch('sys.version_info', new=(2, 7, 12, 'final', 0))
    def test_unverified(self, HTTPSConnection, create_unverified_context):
        # no cert, verify=False, no timeout
        session = koji.compatrequests.Session()
        url = 'https://www.fakedomain234234.org/KOJIHUB?a=1&b=2'
        uri = urlparse.urlsplit(url)
        context = mock.MagicMock()
        create_unverified_context.return_value = context

        cnx = session.get_connection(uri, None, False, None)
        create_unverified_context.assert_called_once()
        HTTPSConnection.assert_called_once_with('www.fakedomain234234.org', 443, context=context)
        key = ('https', 'www.fakedomain234234.org', None, False, None)
        self.assertEqual(session.connection, (key, cnx))

    @mock.patch('httplib.HTTPSConnection')
    @mock.patch('sys.version_info', new=(2, 4, 3, 'final', 0))
    def test_unverified_compat(self, HTTPSConnection):
        # no cert, verify=False, no timeout
        session = koji.compatrequests.Session()
        url = 'https://www.fakedomain234234.org/KOJIHUB?a=1&b=2'
        uri = urlparse.urlsplit(url)

        cnx = session.get_connection(uri, None, False, None)
        HTTPSConnection.assert_called_once_with('www.fakedomain234234.org', 443)
        key = ('https', 'www.fakedomain234234.org', None, False, None)
        self.assertEqual(session.connection, (key, cnx))

    @mock.patch('ssl._create_unverified_context')
    @mock.patch('ssl.SSLContext')
    @mock.patch('httplib.HTTPSConnection')
    @mock.patch('sys.version_info', new=(2, 7, 12, 'final', 0))
    def test_verify(self, HTTPSConnection, SSLContext, create_unverified_context):
        # no cert, no timeout
        session = koji.compatrequests.Session()
        url = 'https://www.fakedomain234234.org/KOJIHUB?a=1&b=2'
        uri = urlparse.urlsplit(url)
        context = mock.MagicMock()
        SSLContext.return_value = context
        verify = '/path/to/verify/cert'

        cnx = session.get_connection(uri, None, verify, None)
        create_unverified_context.assert_not_called()
        SSLContext.assert_called_once()
        context.load_verify_locations.called_once_with(cafile=verify)
        HTTPSConnection.assert_called_once_with('www.fakedomain234234.org', 443, context=context)
        key = ('https', 'www.fakedomain234234.org', None, verify, None)
        self.assertEqual(session.connection, (key, cnx))

    @mock.patch('ssl._create_unverified_context')
    @mock.patch('ssl.SSLContext')
    @mock.patch('httplib.HTTPSConnection')
    @mock.patch('sys.version_info', new=(2, 4, 3, 'final', 0))
    def test_verify_compat(self, HTTPSConnection, SSLContext, create_unverified_context):
        # no cert, no timeout
        session = koji.compatrequests.Session()
        url = 'https://www.fakedomain234234.org/KOJIHUB?a=1&b=2'
        uri = urlparse.urlsplit(url)
        verify = '/path/to/verify/cert'

        cnx = session.get_connection(uri, None, verify, None)
        create_unverified_context.assert_not_called()
        SSLContext.assert_not_called()
        HTTPSConnection.assert_called_once_with('www.fakedomain234234.org', 443, cert_file=verify)
        key = ('https', 'www.fakedomain234234.org', None, verify, None)
        self.assertEqual(session.connection, (key, cnx))
