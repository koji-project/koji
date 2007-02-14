# python library

# db utilities for koji
# Copyright (c) 2005-2007 Red Hat
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


import sys
import pgdb
import time
from pgdb import _quoteparams
assert pgdb.threadsafety >= 1
import context

## Globals ##
_DBopts = None
# A persistent connection to the database.
# A new connection will be created whenever
# Apache forks a new worker, and that connection
# will be used to service all requests handled
# by that worker.
# This probably doesn't need to be a ThreadLocal
# since Apache is not using threading,
# but play it safe anyway.
_DBconn = context.ThreadLocal()

class DBWrapper:
    def __init__(self, cnx, debug=False):
        self.cnx = cnx
        self.debug = debug

    def __getattr__(self, key):
        if not self.cnx:
            raise StandardError, 'connection is closed'
        return getattr(self.cnx, key)

    def cursor(self, *args, **kw):
        if not self.cnx:
            raise StandardError, 'connection is closed'
        return CursorWrapper(self.cnx.cursor(*args, **kw),self.debug)

    def close(self):
        # Rollback any uncommitted changes and clear the connection so
        # this DBWrapper is no longer usable after close()
        if not self.cnx:
            raise StandardError, 'connection is closed'
        self.cnx.rollback()
        self.cnx = None

class CursorWrapper:
    def __init__(self, cursor, debug=False):
        self.cursor = cursor
        self.debug = debug

    def __getattr__(self, key):
        return getattr(self.cursor, key)

    def _timed_call(self, method, args, kwargs):
        if self.debug:
            start = time.time()
        ret = getattr(self.cursor,method)(*args,**kwargs)
        if self.debug:
            sys.stderr.write("%s operation completed in %.4f seconds\n" %
                            (method, time.time() - start))
            sys.stderr.flush()
        return ret

    def fetchone(self,*args,**kwargs):
        return self._timed_call('fetchone',args,kwargs)

    def fetchall(self,*args,**kwargs):
        return self._timed_call('fetchall',args,kwargs)

    def execute(self, operation, parameters=()):
        if self.debug:
            sys.stderr.write(_quoteparams(operation,parameters))
            sys.stderr.write("\n")
            sys.stderr.flush()
            start = time.time()
        ret = self.cursor.execute(operation, parameters)
        if self.debug:
            sys.stderr.write("Execute operation completed in %.4f seconds\n" %
                            (time.time() - start))
            sys.stderr.flush()
        return ret


## Functions ##
def provideDBopts(**opts):
    global _DBopts
    if _DBopts is None:
        _DBopts = opts

def setDBopts(**opts):
    global _DBopts
    _DBopts = opts

def getDBopts():
    return _DBopts

def connect(debug=False):
    global _DBconn
    if hasattr(_DBconn, 'conn'):
        # Make sure the previous transaction has been
        # closed.  This is safe to call multiple times.
        conn = _DBconn.conn
        conn.rollback()
    else:
        opts = _DBopts
        if opts is None:
            opts = {}
        conn = pgdb.connect(**opts)
        # XXX test
        # return conn
        _DBconn.conn = conn

    return DBWrapper(conn, debug)

if __name__ == "__main__":
    setDBopts( database = "test", user = "test")
    print "This is a Python library"
