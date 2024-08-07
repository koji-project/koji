import io
import mock
import time
import unittest

import koji
from kojihub import kojixmlrpc, db
from koji.xmlrpcplus import Fault


'''
These tests simulate the connection between client and hub by using a fake
python_requests session that passes directly through to the hub code.

The goal of these tests is to validate communication between client and hub
'''


class FakeClient(koji.ClientSession):

    def __init__(self, baseurl, opts=None, sinfo=None, auth_method=None):
        super(FakeClient, self).__init__(baseurl, opts=opts, sinfo=sinfo, auth_method=auth_method)

    def new_session(self):
        self.rsession = FakeReqSession(self)


class FakeReqSession:

    def __init__(self, client_session):
        self.client_session = client_session

    def close(self):
        pass

    def post(self, handler, **kwargs):
        headers = kwargs['headers']
        request = kwargs['data']
        data, status, rheaders = self.do_call(headers, request)
        self.last = FakeReqResult(self, data, status, rheaders)
        return self.last

    def do_call(self, headers, request):
        _nonlocal = {}

        def start_response(status, headers):
            _nonlocal['status'] = status
            _nonlocal['headers'] = headers

        # set up fake env dict
        environ = {}
        environ['SCRIPT_FILENAME'] = kojixmlrpc.__file__
        environ['wsgi.url_scheme'] = 'https'
        environ['SERVER_NAME'] = 'myserver'
        environ['SERVER_PORT'] = '443'
        environ['REQUEST_METHOD'] = 'POST'
        environ['CONTENT_TYPE'] = 'text/xml'

        for k in headers:
            k2 = 'HTTP_' + k.upper().replace('-', '_')
            environ[k2] = headers[k]

        # environ['wsgi.input'] = io.StringIO(request)
        environ['wsgi.input'] = io.BytesIO(request)
        data = kojixmlrpc.application(environ, start_response)
        data = data[0]
        return data, _nonlocal['status'], _nonlocal['headers']


class FakeReqResult:

    def __init__(self, rsession, data, status, headers):
        self.rsession = rsession
        self.data = data
        self.status = status
        self.headers = dict(headers)

    def raise_for_status(self):
        pass
        # TODO?

    def iter_content(self, chunk_size=1):
        yield self.data

    def close(self):
        pass
        # TODO?


QP = db.QueryProcessor


class TestClientSession(unittest.TestCase):

    def setUp(self):
        self.context = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()
        self.session = FakeClient('https://bad.server/')
        self.QueryProcessor = mock.patch('kojihub.auth.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self._dml = mock.patch('kojihub.db._dml').start()
        self.query_execute = mock.MagicMock()
        self.query_executeOne = mock.MagicMock()
        self.query_singleValue = mock.MagicMock()
        self.queries = []

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = self.query_execute
        query.executeOne = self.query_executeOne
        query.singleValue = self.query_singleValue
        self.queries.append(query)
        return query

    def test_echo(self):
        args = ['OK 123', 456, {}]
        result = self.session.echo(*args)
        self.assertEqual(result, args)
        self.assertEqual(len(self.queries), 0)

    def test_sinfo(self):
        self.session.callnum = 1
        self.session.sinfo = {
            'session-id': 123,
            'session-key': 'MYKEY456',
        }
        session_data = {
            'expired': False,
            'renew_ts': time.time(),
            'callnum': None,
            'user_id': 1,
            'authtype': koji.AUTHTYPES['SSL'],
            'master': None,
            'exclusive': True,  # avoids a third query
        }
        user_data = {'status': koji.USER_STATUS['NORMAL']}
        self.query_executeOne.side_effect = [session_data, user_data]

        args = ['OK 123', 456, {}]
        result = self.session.echo(*args)
        self.assertEqual(result, args)
        self.assertEqual(len(self.queries), 2)

    def test_sequence_error(self):
        self.session.callnum = 1
        self.session.sinfo = {
            'session-id': 123,
            'session-key': 'MYKEY456',
        }
        session_data = {
            'expired': False,
            'renew_ts': time.time(),
            'callnum': 2,  # higher than what client reports
            'user_id': 1,
            'authtype': koji.AUTHTYPES['SSL'],
            'master': None,
            'exclusive': True,  # avoids a third query
        }
        user_data = {'status': koji.USER_STATUS['NORMAL']}
        self.query_executeOne.side_effect = [session_data, user_data]

        with self.assertRaises(koji.SequenceError):
            self.session.echo('bad')

    def test_retry_error(self):
        self.session.callnum = 1
        self.session.sinfo = {
            'session-id': 123,
            'session-key': 'MYKEY456',
        }
        session_data = {
            'expired': False,
            'renew_ts': time.time(),
            'callnum': 1,  # same as what client reports
            'user_id': 1,
            'authtype': koji.AUTHTYPES['SSL'],
            'master': None,
            'exclusive': True,  # avoids a third query
        }
        user_data = {'status': koji.USER_STATUS['NORMAL']}
        self.query_executeOne.side_effect = [session_data, user_data]

        with self.assertRaises(koji.RetryError):
            self.session.echo('bad')

    def test_error(self):
        with self.assertRaises(koji.GenericError):
            self.session.error()
        self.assertEqual(len(self.queries), 0)

    def test_fault(self):
        with self.assertRaises(Fault):
            self.session.fault()
        self.assertEqual(len(self.queries), 0)

    TEST_VER_HDR = [('Koji-Version', '1.2.3')]

    @mock.patch('kojihub.kojixmlrpc.GLOBAL_HEADERS', new=TEST_VER_HDR)
    def test_hub_version(self):
        self.session.echo('test')
        self.assertEqual(self.session.hub_version_str, '1.2.3')
        self.assertEqual(self.session.hub_version, (1, 2, 3))


# the end
