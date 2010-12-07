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
# Modified by Dan Williams <dcbw@redhat.com>
# Further modified by Mike Bonnet <mikeb@redhat.com>

import os, sys
import SSLCommon
import urllib
import xmlrpclib

__version__='0.12'

class PlgSSL_Transport(xmlrpclib.Transport):

    user_agent = "pyOpenSSL_XMLRPC/%s - %s" % (__version__, xmlrpclib.Transport.user_agent)

    def __init__(self, ssl_context, timeout=None, use_datetime=0):
        if sys.version_info[:3] >= (2, 5, 0):
            xmlrpclib.Transport.__init__(self, use_datetime)
        self.ssl_ctx=ssl_context
        self._timeout = timeout
        self._https = None

    def make_connection(self, host):
        # Handle username and password.
        try:
            host, extra_headers, x509 = self.get_host_info(host)
        except AttributeError:
            # Yay for Python 2.2
            pass
        _host, _port = urllib.splitport(host)
        if hasattr(xmlrpclib.Transport, 'single_request'):
            cnx_class = SSLCommon.PlgHTTPSConnection
        else:
            cnx_class = SSLCommon.PlgHTTPS
        self._https = cnx_class(_host, (_port and int(_port) or 443), ssl_context=self.ssl_ctx, timeout=self._timeout)
        return self._https

    def close(self):
        if self._https:
            self._https.close()
            self._https = None


class Plg_ClosableTransport(xmlrpclib.Transport):
    """Override make_connection so we can close it."""
    def __init__(self):
        self._http = None

    def make_connection(self, host):
        # create a HTTP connection object from a host descriptor
        import httplib
        host, extra_headers, x509 = self.get_host_info(host)
        self._http = httplib.HTTP(host)
        return self._http

    def close(self):
        if self._http:
            self._http.close()
            self._http = None


class PlgXMLRPCServerProxy(xmlrpclib.ServerProxy):
    def __init__(self, uri, certs, timeout=None, verbose=0, allow_none=0):
        if certs and len(certs) > 0:
            self.ctx = SSLCommon.CreateSSLContext(certs)
            self._transport = PlgSSL_Transport(ssl_context=self.ctx, timeout=timeout)
        else:
            self._transport = Plg_ClosableTransport()
        xmlrpclib.ServerProxy.__init__(self, uri, transport=self._transport,
                                       verbose=verbose, allow_none=allow_none)

    def cancel(self):
        self._transport.close()


###########################################################
# Testing stuff
###########################################################


import threading
import time
import random
import OpenSSL
import socket

client_start = False

threadlist_lock = threading.Lock()
threadlist = {}

class TestClient(threading.Thread):
    def __init__(self, certs, num, tm):
        self.server = PlgXMLRPCServerProxy("https://127.0.0.1:8886", certs, timeout=20)
        self.num = i
        self.tm = tm
        threading.Thread.__init__(self)

    def run(self):
        while not client_start:
            time.sleep(0.05)
        i = 0
        while i < 5:
            reply = None
            try:
                reply = self.server.ping(self.num, i)
            except OpenSSL.SSL.Error, e:
                reply = "OpenSSL Error (%s)" % e
            except socket.timeout, e:
                reply = "Socket timeout (%s)" % e
                threadlist_lock.acquire()
                self.tm.inc()
                threadlist_lock.release()
            print "TRY(%d / %d): %s" % (self.num, i, reply)
            time.sleep(0.05)
            i = i + 1
        threadlist_lock.acquire()
        del threadlist[self]
        threadlist_lock.release()

class TimeoutCounter:
    def __init__(self):
        self._timedout = 0
        self._lock = threading.Lock();

    def inc(self):
        self._lock.acquire()
        self._timedout = self._timedout + 1
        self._lock.release()

    def get(self):
        return self._timedout

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print "Usage: python XMLRPCServerProxy.py key_and_cert ca_cert peer_ca_cert"
        sys.exit(1)

    certs = {}
    certs['key_and_cert'] = sys.argv[1]
    certs['ca_cert'] = sys.argv[2]
    certs['peer_ca_cert'] = sys.argv[3]

    tm = TimeoutCounter()
    i = 100
    while i > 0:
        t = TestClient(certs, i, tm)
        threadlist[t] = None
        print "Created thread %d." % i
        t.start()
        i = i - 1

    time.sleep(3)
    print "Unleashing threads."
    client_start = True
    while True:
        try:
            time.sleep(0.25)
            threadlist_lock.acquire()
            if len(threadlist) == 0:
                break
            threadlist_lock.release()
        except KeyboardInterrupt:
            os._exit(0)
    print "All done. (%d timed out)" % tm.get()

