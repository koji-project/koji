# common server code for koji
#
# Copyright (c) 2012-2014 Red Hat, Inc.
#
#    Koji is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation;
#    version 2.1 of the License.
#
#    This software is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public
#    License along with this software; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# Authors:
#       Mike McLean <mikem@redhat.com>

import koji
import sys
import traceback
from koji.util import LazyDict

try:
    from mod_python import apache
except ImportError:
    apache = None


class ServerError(Exception):
    """Base class for our server-side-only exceptions"""

class ServerRedirect(ServerError):
    """Used to handle redirects"""


class WSGIWrapper(object):
    """A very thin wsgi compat layer for mod_python

    This class is highly specific to koji and is not fit for general use.
    It does not support the full wsgi spec
    """

    def __init__(self, req):
        self.req = req
        self._env = None
        host, port = req.connection.remote_addr
        environ = {
            'REMOTE_ADDR' : req.connection.remote_ip,
            # or remote_addr[0]?
            # or req.get_remote_host(apache.REMOTE_NOLOOKUP)?
            'REMOTE_PORT' : str(req.connection.remote_addr[1]),
            'REMOTE_USER' : req.user,
            'REQUEST_METHOD' : req.method,
            'REQUEST_URI' : req.uri,
            'PATH_INFO' : req.path_info,
            'SCRIPT_FILENAME' : req.filename,
            'QUERY_STRING' : req.args or '',
            'SERVER_NAME' : req.hostname,
            'SERVER_PORT' : str(req.connection.local_addr[1]),
            'wsgi.version' : (1, 0),
            'wsgi.input' : InputWrapper(req),
            'wsgi.errors' : sys.stderr,
            #TODO - file_wrapper support
        }
        environ = LazyDict(environ)
        environ.lazyset('wsgi.url_scheme', self.get_scheme, [])
        environ.lazyset('modpy.env', self.env, [])
        environ.lazyset('modpy.opts', req.get_options, [])
        environ.lazyset('modpy.conf', req.get_config, [])
        environ.lazyset('SCRIPT_NAME', self.script_name, [], cache=True)
        env_keys = ['SSL_CLIENT_VERIFY', 'HTTPS', 'SSL_CLIENT_S_DN']
        for key in env_keys:
            environ.lazyset(key, self.envget, [key])
        # The component of the DN used for the username is usually the CN,
        # but it is configurable.
        # Allow retrieval of some common DN components from the environment.
        for comp in ['C', 'ST', 'L', 'O', 'OU', 'CN', 'Email']:
            key = 'SSL_CLIENT_S_DN_' + comp
            environ.lazyset(key, self.envget, [key])
        #gather the headers we care about
        for key in req.headers_in:
            k2 = key.upper()
            k2 = k2.replace('-', '_')
            if k2 not in ['CONTENT_TYPE', 'CONTENT_LENGTH']:
                k2 = 'HTTP_' + k2
            environ[k2] = req.headers_in[key]
        self.environ = environ
        self.set_headers = False

    def env(self):
        if self._env is None:
            self.req.add_common_vars()
            self._env = self.req.subprocess_env
        return self._env

    def envget(self, *args):
        return self.env().get(*args)

    def script_name(self):
        uri = self.req.uri
        path_info = self.req.path_info
        if uri.endswith(path_info):
            uri = uri[:-len(path_info)]
            uri = uri.rstrip('/')
        return uri

    def get_scheme(self):
        if self.envget('HTTPS') in ('yes', 'on', '1'):
            return 'https'
        else:
            return 'http'

    def no_write(self, string):
        """a fake write() callable returned by start_response

        we don't use the write() callable in koji, so it will raise an error if called
        """
        raise RuntimeError, "wsgi write() callable not supported"

    def start_response(self, status, headers, exc_info=None):
        #XXX we don't deal with exc_info
        if self.set_headers:
            raise RuntimeError, "start_response() already called"
        self.req.status = int(status[:3])
        for key, val in headers:
            if key.lower() == 'content-length':
                self.req.set_content_length(int(val))
            elif key.lower() == 'content-type':
                self.req.content_type = val
            else:
                self.req.headers_out.add(key, val)
        self.set_headers = True
        return self.no_write

    def run(self, handler):
        try:
            result = handler(self.environ, self.start_response)
            self.write_result(result)
            return apache.OK
        except:
            sys.stderr.write(''.join(traceback.format_exception(*sys.exc_info())))
            sys.stderr.flush()
            raise apache.SERVER_RETURN, apache.HTTP_INTERNAL_SERVER_ERROR

    def write_result(self, result):
        """called by run() to handle the application's result value"""
        req = self.req
        write = req.write
        if self.set_headers:
            for chunk in result:
                write(chunk)
        else:
            #slower version -- need to check for set_headers
            for chunk in result:
                if chunk and not self.set_headers:
                    raise RuntimeError, "write() called before start_response()"
                write(chunk)
        if not req.bytes_sent:
            #application sent nothing back
            req.set_content_length(0)



class InputWrapper(object):

    def __init__(self, req):
        self.req = req

    def close(self):
        pass

    def read(self, size=-1):
        return self.req.read(size)

    def readline(self):
        return self.req.readline()

    def readlines(self, hint=-1):
        return self.req.readlines(hint)

    def __iter__(self):
        line = self.readline()
        while line:
            yield line
            line = self.readline()
