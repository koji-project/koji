# python library

# db utilities for koji
# Copyright (c) 2005-2014 Red Hat, Inc.
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


from __future__ import absolute_import

import logging
# import psycopg2.extensions
# # don't convert timestamp fields to DateTime objects
# del psycopg2.extensions.string_types[1114]
# del psycopg2.extensions.string_types[1184]
# del psycopg2.extensions.string_types[1082]
# del psycopg2.extensions.string_types[1083]
# del psycopg2.extensions.string_types[1266]
import re
import sys
import time
import traceback

import psycopg2

from . import context

POSITIONAL_RE = re.compile(r'%[a-z]')
NAMED_RE = re.compile(r'%\(([^\)]+)\)[a-z]')

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
            raise Exception('connection is closed')
        return getattr(self.cnx, key)

    def cursor(self, *args, **kw):
        if not self.cnx:
            raise Exception('connection is closed')
        return CursorWrapper(self.cnx.cursor(*args, **kw))

    def close(self):
        # Rollback any uncommitted changes and clear the connection so
        # this DBWrapper is no longer usable after close()
        if not self.cnx:
            raise Exception('connection is closed')
        self.cnx.cursor().execute('ROLLBACK')
        # We do this rather than cnx.rollback to avoid opening a new transaction
        # If our connection gets recycled cnx.rollback will be called then.
        self.cnx = None


class CursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor
        self.logger = logging.getLogger('koji.db')

    def __getattr__(self, key):
        return getattr(self.cursor, key)

    def _timed_call(self, method, args, kwargs):
        start = time.time()
        ret = getattr(self.cursor, method)(*args, **kwargs)
        self.logger.debug("%s operation completed in %.4f seconds", method, time.time() - start)
        return ret

    def fetchone(self, *args, **kwargs):
        return self._timed_call('fetchone', args, kwargs)

    def fetchall(self, *args, **kwargs):
        return self._timed_call('fetchall', args, kwargs)

    def quote(self, operation, parameters):
        if hasattr(self.cursor, "mogrify"):
            quote = self.cursor.mogrify
        else:
            def quote(a, b):
                return a % b
        try:
            return quote(operation, parameters)
        except Exception:
            self.logger.exception(
                'Unable to quote query:\n%s\nParameters: %s', operation, parameters)
            return "INVALID QUERY"

    def preformat(self, sql, params):
        """psycopg2 requires all variable placeholders to use the string (%s) datatype,
        regardless of the actual type of the data. Format the sql string to be compliant.
        It also requires IN parameters to be in tuple rather than list format."""
        sql = POSITIONAL_RE.sub(r'%s', sql)
        sql = NAMED_RE.sub(r'%(\1)s', sql)
        if isinstance(params, dict):
            for name, value in params.items():
                if isinstance(value, list):
                    params[name] = tuple(value)
        else:
            if isinstance(params, tuple):
                params = list(params)
            for i, item in enumerate(params):
                if isinstance(item, list):
                    params[i] = tuple(item)
        return sql, params

    def execute(self, operation, parameters=()):
        debug = self.logger.isEnabledFor(logging.DEBUG)
        operation, parameters = self.preformat(operation, parameters)
        if debug:
            self.logger.debug(self.quote(operation, parameters))
            start = time.time()
        try:
            ret = self.cursor.execute(operation, parameters)
        except Exception:
            self.logger.error('Query failed. Query was: %s', self.quote(operation, parameters))
            raise
        if debug:
            self.logger.debug("Execute operation completed in %.4f seconds", time.time() - start)
        return ret


## Functions ##
def provideDBopts(**opts):
    global _DBopts
    if _DBopts is None:
        _DBopts = dict([i for i in opts.items() if i[1] is not None])


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
        except psycopg2.Error:
            del _DBconn.conn
    # create a fresh connection
    opts = _DBopts
    if opts is None:
        opts = {}
    try:
        if 'dsn' in opts:
            conn = psycopg2.connect(dsn=opts['dsn'])
        else:
            conn = psycopg2.connect(**opts)
        conn.set_client_encoding('UTF8')
    except Exception:
        logger.error(''.join(traceback.format_exception(*sys.exc_info())))
        raise
    # XXX test
    # return conn
    _DBconn.conn = conn

    return DBWrapper(conn)
