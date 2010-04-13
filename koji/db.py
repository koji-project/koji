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


import logging
import sys
import pgdb
import time
import traceback
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
    def __init__(self, cnx):
        self.cnx = cnx

    def __getattr__(self, key):
        if not self.cnx:
            raise StandardError, 'connection is closed'
        return getattr(self.cnx, key)

    def cursor(self, *args, **kw):
        if not self.cnx:
            raise StandardError, 'connection is closed'
        return CursorWrapper(self.cnx.cursor(*args, **kw))

    def close(self):
        # Rollback any uncommitted changes and clear the connection so
        # this DBWrapper is no longer usable after close()
        if not self.cnx:
            raise StandardError, 'connection is closed'
        self.cnx.cursor().execute('ROLLBACK')
        #We do this rather than cnx.rollback to avoid opening a new transaction
        #If our connection gets recycled cnx.rollback will be called then.
        self.cnx = None


class CursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor
        self.logger = logging.getLogger('koji.db')

    def __getattr__(self, key):
        return getattr(self.cursor, key)

    def _timed_call(self, method, args, kwargs):
        start = time.time()
        ret = getattr(self.cursor,method)(*args,**kwargs)
        self.logger.debug("%s operation completed in %.4f seconds", method, time.time() - start)
        return ret

    def fetchone(self,*args,**kwargs):
        return self._timed_call('fetchone',args,kwargs)

    def fetchall(self,*args,**kwargs):
        return self._timed_call('fetchall',args,kwargs)

    def execute(self, operation, parameters=()):
        debug = self.logger.isEnabledFor(logging.DEBUG)
        if debug:
            self.logger.debug(_quoteparams(operation,parameters))
            start = time.time()
        ret = self.cursor.execute(operation, parameters)
        if debug:
            self.logger.debug("Execute operation completed in %.4f seconds", time.time() - start)
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

def connect():
    logger = logging.getLogger('koji.db')
    global _DBconn
    if hasattr(_DBconn, 'conn'):
        # Make sure the previous transaction has been
        # closed.  This is safe to call multiple times.
        conn = _DBconn.conn
        try:
            # Under normal circumstances, the last use of this connection
            # will have issued a raw ROLLBACK to close the transaction. To
            # avoid 'no transaction in progress' warnings (depending on postgres
            # configuration) we open a new one here.
            # Should there somehow be a transaction in progress, a second
            # BEGIN will be a harmless no-op, though there may be a warning.
            conn.cursor().execute('BEGIN')
            conn.rollback()
            return DBWrapper(conn)
        except pgdb.Error:
            del _DBconn.conn
    #create a fresh connection
    opts = _DBopts
    if opts is None:
        opts = {}
    try:
        conn = pgdb.connect(**opts)
    except Exception:
        logger.error(''.join(traceback.format_exception(*sys.exc_info())))
        raise
    # XXX test
    # return conn
    _DBconn.conn = conn

    return DBWrapper(conn)

if __name__ == "__main__":
    setDBopts( database = "test", user = "test")
    print "This is a Python library"
