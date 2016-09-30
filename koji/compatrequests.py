"""
koji.compatrequests
~~~~~~~~~~~~~~~~~~~

This module contains a *very limited* partial implemention of the requests
module that is based on the older codepaths in koji. It only provides
the bits that koji needs.
"""


class Session(object):

    def __init__(self):
        self.connection = None

    def post(self, url, data=None, headers=None, stream=None, verify=None,
                cert=None, timeout=None):
        cnx = self.get_connection(url, cert, timeout)
        # TODO get handler from url
        cnx.putrequest('POST', handler)
        if headers:
            for k in headers:
                cnx.putheader(k, headers[k])
        cnx.endheaders()
        if data is not None:
            cnx.send(data)
        response = cnx.getresponse()
        return Response(self, response)

    def get_connection(self, url, cert, timeout):
        key = (url, cert, timeout)
        if self.connection and self.opts.get('keepalive'):
            if key == self.connection[0]:
                cnx = self._connection[1]
                if getattr(cnx, 'sock', None):
                    return cnx
        # Otherwise we make a new one
        uri = urlparse.urlsplit(url)
        scheme = uri[0]
        host, port = urllib.splitport(uri[1])
        path = uri[2]
        default_port = 80
        if cert:
            ctx = ssl.SSLCommon.CreateSSLContext(cert) #XXX
            cnxOpts = {'ssl_context' : ctx}
            cnxClass = ssl.SSLCommon.PlgHTTPSConnection
            default_port = 443
        elif scheme == 'https':
            cnxOpts = {}
            if sys.version_info[:3] >= (2, 7, 9):
                ctx = pyssl._create_unverified_context()
                # TODO - we should default to verifying where possible
                cnxOpts['context'] = ctx
            cnxClass = httplib.HTTPSConnection
            default_port = 443
        elif scheme == 'http':
            cnxOpts = {}
            cnxClass = httplib.HTTPConnection
        else:
            raise IOError, "unsupported protocol: %s" % scheme

        timeout_compat = False
        if timeout:
            if sys.version_info[:3] < (2, 6, 0) and 'ssl_context' not in cnxOpts:
                timeout_compat = True
            else:
                cnxOpts['timeout'] = timeout
        # no need to close connection
        cnx = cnxClass(host, port, **cnxOpts)
        self.connection = (key, cnx)
        if timeout_compat:
            # in python < 2.6 httplib does not support the timeout option
            # but socket supports it since 2.3
            cnx.connect()
            cnx.sock.settimeout(timeout)

    def close_connection(self):
        if self.connection:
            self.connection[1].close()
            self.connection = None


class Response(object):

    def __init__(self, session, response):
        self.session = session
        self.response = response

    def iter_content(self, blocksize=8192):
        # should we check this in Session.post()?
        # should we even check this here?
        if self.response.status != 200:
            if (self.response.getheader("content-length", 0)):
                self.response.read()
            # XXX wrong exception
            raise xmlrpclib.ProtocolError(self._host + handler,
                        response.status, response.reason, response.msg)
        while True:
            chunk = response.read(blocksize)
            if not chunk:
                break
            yield chunk



