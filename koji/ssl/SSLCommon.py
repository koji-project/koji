# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Copyright 2005 Dan Williams <dcbw@redhat.com> and Red Hat, Inc.

import os, sys
from OpenSSL import SSL
import SSLConnection
import httplib
import socket
import SocketServer

def our_verify(connection, x509, errNum, errDepth, preverifyOK):
    # print "Verify: errNum = %s, errDepth = %s, preverifyOK = %s" % (errNum, errDepth, preverifyOK)

    # preverifyOK should tell us whether or not the client's certificate
    # correctly authenticates against the CA chain
    return preverifyOK


def CreateSSLContext(certs):
    key_and_cert = certs['key_and_cert']
    ca_cert = certs['ca_cert']
    peer_ca_cert = certs['peer_ca_cert']
    for f in key_and_cert, ca_cert, peer_ca_cert:
        if f and not os.access(f, os.R_OK):
            raise StandardError, "%s does not exist or is not readable" % f

    ctx = SSL.Context(SSL.SSLv3_METHOD)   # SSLv3 only
    ctx.use_certificate_file(key_and_cert)
    ctx.use_privatekey_file(key_and_cert)
    ctx.load_client_ca(ca_cert)
    ctx.load_verify_locations(peer_ca_cert)
    verify = SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT
    ctx.set_verify(verify, our_verify)
    ctx.set_verify_depth(10)
    ctx.set_options(SSL.OP_NO_SSLv2 | SSL.OP_NO_TLSv1)
    return ctx



class PlgBaseServer(SocketServer.ThreadingTCPServer):
    allow_reuse_address = 1

    def __init__(self, server_addr, req_handler):
        self._quit = False
        self.allow_reuse_address = 1
        SocketServer.ThreadingTCPServer.__init__(self, server_addr, req_handler)

    def stop(self):
        self._quit = True

    def serve_forever(self):
        while not self._quit:
            self.handle_request()
        self.server_close()


class PlgBaseSSLServer(PlgBaseServer):
    """ SSL-enabled variant """

    def __init__(self, server_address, req_handler, certs, timeout=None):
        self._timeout = timeout
        self.ssl_ctx = CreateSSLContext(certs)

        PlgBaseServer.__init__(self, server_address, req_handler)

        sock = socket.socket(self.address_family, self.socket_type)
        con = SSL.Connection(self.ssl_ctx, sock)
        self.socket = SSLConnection.SSLConnection(con)
        if sys.version_info[:3] >= (2, 3, 0):
            self.socket.settimeout(self._timeout)
        self.server_bind()
        self.server_activate()

        host, port = self.socket.getsockname()[:2]
        self.server_name = socket.getfqdn(host)
        self.server_port = port


class PlgHTTPSConnection(httplib.HTTPConnection):
    "This class allows communication via SSL."

    response_class = httplib.HTTPResponse

    def __init__(self, host, port=None, ssl_context=None, strict=None, timeout=None):
        httplib.HTTPConnection.__init__(self, host, port, strict)
        self.ssl_ctx = ssl_context
        self._timeout = timeout

    def connect(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        con = SSL.Connection(self.ssl_ctx, sock)
        self.sock = SSLConnection.SSLConnection(con)
        if sys.version_info[:3] >= (2, 3, 0):
            self.sock.settimeout(self._timeout)
        self.sock.connect((self.host, self.port))


class PlgHTTPS(httplib.HTTP):
    """Compatibility with 1.5 httplib interface

    Python 1.5.2 did not have an HTTPS class, but it defined an
    interface for sending http requests that is also useful for
    https.
    """

    _http_vsn = 11
    _http_vsn_str = 'HTTP/1.1'

    _connection_class = PlgHTTPSConnection

    def __init__(self, host='', port=None, ssl_context=None, strict=None, timeout=None):
        self._setup(self._connection_class(host, port, ssl_context, strict, timeout))

