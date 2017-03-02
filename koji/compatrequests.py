"""
koji.compatrequests
~~~~~~~~~~~~~~~~~~~

This module contains a *very limited* partial implemention of the requests
module that is based on the older codepaths in koji. It only provides
the bits that koji needs.
"""

import httplib
import urlparse
import urllib
import sys
import ssl.SSLCommon
try:
    from ssl import ssl as pyssl
except ImportError:  # pragma: no cover
    pass


class Session(object):

    def __init__(self):
        self.connection = None

    def post(self, url, data=None, headers=None, stream=None, verify=None,
                cert=None, timeout=None):
        uri = urlparse.urlsplit(url)
        if uri[3]:
            handler = "%s?%s" % (uri[2], uri[3])
        else:
            handler = uri[2]
        cnx = self.get_connection(uri, cert, verify, timeout)
        #cnx.set_debuglevel(1)
        cnx.putrequest('POST', handler)
        if headers:
            for k in headers:
                cnx.putheader(k, headers[k])
        cnx.endheaders()
        if data is not None:
            cnx.send(data)
        response = cnx.getresponse()
        return Response(self, response)

    def get_connection(self, uri, cert, verify, timeout):
        scheme = uri[0]
        host, port = urllib.splitport(uri[1])
        key = (scheme, host, cert, verify, timeout)
        #if self.connection and self.opts.get('keepalive'):
        if self.connection:   # XXX honor keepalive
            if key == self.connection[0]:
                cnx = self.connection[1]
                if getattr(cnx, 'sock', None):
                    return cnx
        # Otherwise we make a new one
        default_port = 80
        certs = {}
        if isinstance(verify, basestring):
            certs['peer_ca_cert'] = verify
        if cert:
            certs['key_and_cert'] = cert
            ctx = ssl.SSLCommon.CreateSSLContext(certs)
            cnxOpts = {'ssl_context' : ctx}
            cnxClass = ssl.SSLCommon.PlgHTTPSConnection
            default_port = 443
        elif scheme == 'https':
            cnxOpts = {}
            if verify:
                if sys.version_info[:3] >= (2, 7, 9):
                    try:
                        proto = pyssl.PROTOCOL_TLS
                    except AttributeError:
                        proto = pyssl.PROTOCOL_SSLv23
                    ctx = pyssl.SSLContext(proto)
                    ctx.load_verify_locations(cafile=verify)
                    ctx.verify_mode = pyssl.CERT_REQUIRED
                    cnxOpts['context'] = ctx
                else:
                    cnxOpts['cert_file'] = verify
            elif verify is None:
                # not specified, leave as default
                pass
            elif sys.version_info[:3] >= (2, 7, 9):
                # no verify
                ctx = pyssl._create_unverified_context()
                cnxOpts['context'] = ctx
            cnxClass = httplib.HTTPSConnection
            default_port = 443
        elif scheme == 'http':
            cnxOpts = {}
            cnxClass = httplib.HTTPConnection
        else:
            raise IOError("unsupported protocol: %s" % scheme)

        timeout_compat = False
        if timeout:
            if sys.version_info[:3] < (2, 6, 0) and 'ssl_context' not in cnxOpts:
                timeout_compat = True
            else:
                cnxOpts['timeout'] = timeout
        # no need to close connection
        port = (port and int(port) or default_port)
        cnx = cnxClass(host, port, **cnxOpts)
        self.connection = (key, cnx)
        if timeout_compat:
            # in python < 2.6 httplib does not support the timeout option
            # but socket supports it since 2.3
            cnx.connect()
            cnx.sock.settimeout(timeout)
        return cnx

    def close(self):
        if self.connection:
            self.connection[1].close()
            self.connection = None


class Response(object):

    def __init__(self, session, response):
        self.session = session
        self.response = response

    def raise_for_status(self):
        if self.response.status >= 400:
            raise httplib.HTTPException("HTTP %s: %s" % (self.response.status,
                    self.response.reason))

    def iter_content(self, blocksize=8192):
        # should we check this in Session.post()?
        # should we even check this here?
        if self.response.status != 200:
            if (self.response.getheader("content-length", 0)):
                self.response.read()
            # XXX wrong exception
            raise Exception("Server status: %s" % self.response.status)
        while True:
            chunk = self.response.read(blocksize)
            if not chunk:
                break
            yield chunk

    def close(self):
        self.response.close()



