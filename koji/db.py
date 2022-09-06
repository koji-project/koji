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
import koji
import os
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

import koji.context
context = koji.context.context


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
_DBconn = koji.context.ThreadLocal()

logger = logging.getLogger('koji.db')


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

    def execute(self, operation, parameters=(), log_errors=True):
        debug = self.logger.isEnabledFor(logging.DEBUG)
        operation, parameters = self.preformat(operation, parameters)
        if debug:
            self.logger.debug(self.quote(operation, parameters))
            start = time.time()
        try:
            ret = self.cursor.execute(operation, parameters)
        except Exception:
            if log_errors:
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


def _dml(operation, values, log_errors=True):
    """Run an insert, update, or delete. Return number of rows affected
    If log is False, errors will not be logged. It makes sense only for
    queries which are expected to fail (LOCK NOWAIT)
    """
    c = context.cnx.cursor()
    c.execute(operation, values, log_errors=log_errors)
    ret = c.rowcount
    logger.debug("Operation affected %s row(s)", ret)
    c.close()
    context.commit_pending = True
    return ret


def _fetchMulti(query, values):
    """Run the query and return all rows"""
    c = context.cnx.cursor()
    c.execute(query, values)
    results = c.fetchall()
    c.close()
    return results


def _fetchSingle(query, values, strict=False):
    """Run the query and return a single row

    If strict is true, raise an error if the query returns more or less than
    one row."""
    results = _fetchMulti(query, values)
    numRows = len(results)
    if numRows == 0:
        if strict:
            raise koji.GenericError('query returned no rows')
        else:
            return None
    elif strict and numRows > 1:
        raise koji.GenericError('multiple rows returned for a single row query')
    else:
        return results[0]


def _singleValue(query, values=None, strict=True):
    """Perform a query that returns a single value.

    Note that unless strict is True a return value of None could mean either
    a single NULL value or zero rows returned."""
    if values is None:
        values = {}
    row = _fetchSingle(query, values, strict)
    if row:
        if strict and len(row) > 1:
            raise koji.GenericError('multiple fields returned for a single value query')
        return row[0]
    else:
        # don't need to check strict here, since that was already handled by _singleRow()
        return None


def _multiRow(query, values, fields):
    """Return all rows from "query".  Named query parameters
    can be specified using the "values" map.  Results will be returned
    as a list of maps.  Each map in the list will have a key for each
    element in the "fields" list.  If there are no results, an empty
    list will be returned."""
    return [dict(zip(fields, row)) for row in _fetchMulti(query, values)]


def _singleRow(query, values, fields, strict=False):
    """Return a single row from "query".  Named parameters can be
    specified using the "values" map.  The result will be returned as
    as map.  The map will have a key for each element in the "fields"
    list.  If more than one row is returned and "strict" is true, a
    GenericError will be raised.  If no rows are returned, and "strict"
    is True, a GenericError will be raised.  Otherwise None will be
    returned."""
    row = _fetchSingle(query, values, strict)
    if row:
        return dict(zip(fields, row))
    else:
        # strict enforced by _fetchSingle
        return None


def get_event():
    """Get an event id for this transaction

    We cache the result in context, so subsequent calls in the same transaction will
    get the same event.

    This cache is cleared between the individual calls in a multicall.
    See: https://pagure.io/koji/pull-request/74
    """
    if hasattr(context, 'event_id'):
        return context.event_id
    event_id = _singleValue("SELECT get_event()")
    context.event_id = event_id
    return event_id


def nextval(sequence):
    """Get the next value for the given sequence"""
    data = {'sequence': sequence}
    return _singleValue("SELECT nextval(%(sequence)s)", data, strict=True)


class Savepoint(object):

    def __init__(self, name):
        self.name = name
        _dml("SAVEPOINT %s" % name, {})

    def rollback(self):
        _dml("ROLLBACK TO SAVEPOINT %s" % self.name, {})


class InsertProcessor(object):
    """Build an insert statement

    table - the table to insert into
    data - a dictionary of data to insert (keys = row names)
    rawdata - data to insert specified as sql expressions rather than python values

    does not support query inserts of "DEFAULT VALUES"
    """

    def __init__(self, table, data=None, rawdata=None):
        self.table = table
        self.data = {}
        if data:
            self.data.update(data)
        self.rawdata = {}
        if rawdata:
            self.rawdata.update(rawdata)

    def __str__(self):
        if not self.data and not self.rawdata:
            return "-- incomplete update: no assigns"
        parts = ['INSERT INTO %s ' % self.table]
        columns = sorted(list(self.data.keys()) + list(self.rawdata.keys()))
        parts.append("(%s) " % ', '.join(columns))
        values = []
        for key in columns:
            if key in self.data:
                values.append("%%(%s)s" % key)
            else:
                values.append("(%s)" % self.rawdata[key])
        parts.append("VALUES (%s)" % ', '.join(values))
        return ''.join(parts)

    def __repr__(self):
        return "<InsertProcessor: %r>" % vars(self)

    def set(self, **kwargs):
        """Set data via keyword args"""
        self.data.update(kwargs)

    def rawset(self, **kwargs):
        """Set rawdata via keyword args"""
        self.rawdata.update(kwargs)

    def make_create(self, event_id=None, user_id=None):
        if event_id is None:
            event_id = get_event()
        if user_id is None:
            context.session.assertLogin()
            user_id = context.session.user_id
        self.data['create_event'] = event_id
        self.data['creator_id'] = user_id

    def dup_check(self):
        """Check to see if the insert duplicates an existing row"""
        if self.rawdata:
            logger.warning("Can't perform duplicate check")
            return None
        data = self.data.copy()
        if 'create_event' in self.data:
            # versioned table
            data['active'] = True
            del data['create_event']
            del data['creator_id']
        clauses = ["%s = %%(%s)s" % (k, k) for k in data]
        query = QueryProcessor(columns=list(data.keys()), tables=[self.table],
                               clauses=clauses, values=data)
        if query.execute():
            return True
        return False

    def execute(self):
        return _dml(str(self), self.data)


class UpdateProcessor(object):
    """Build an update statement

    table - the table to insert into
    data - a dictionary of data to insert (keys = row names)
    rawdata - data to insert specified as sql expressions rather than python values
    clauses - a list of where clauses which will be ANDed together
    values - dict of values used in clauses

    does not support the FROM clause
    """

    def __init__(self, table, data=None, rawdata=None, clauses=None, values=None):
        self.table = table
        self.data = {}
        if data:
            self.data.update(data)
        self.rawdata = {}
        if rawdata:
            self.rawdata.update(rawdata)
        self.clauses = []
        if clauses:
            self.clauses.extend(clauses)
        self.values = {}
        if values:
            self.values.update(values)

    def __str__(self):
        if not self.data and not self.rawdata:
            return "-- incomplete update: no assigns"
        parts = ['UPDATE %s SET ' % self.table]
        assigns = ["%s = %%(data.%s)s" % (key, key) for key in self.data]
        assigns.extend(["%s = (%s)" % (key, self.rawdata[key]) for key in self.rawdata])
        parts.append(', '.join(sorted(assigns)))
        if self.clauses:
            parts.append('\nWHERE ')
            parts.append(' AND '.join(["( %s )" % c for c in sorted(self.clauses)]))
        return ''.join(parts)

    def __repr__(self):
        return "<UpdateProcessor: %r>" % vars(self)

    def get_values(self):
        """Returns unified values dict, including data"""
        ret = {}
        ret.update(self.values)
        for key in self.data:
            ret["data." + key] = self.data[key]
        return ret

    def set(self, **kwargs):
        """Set data via keyword args"""
        self.data.update(kwargs)

    def rawset(self, **kwargs):
        """Set rawdata via keyword args"""
        self.rawdata.update(kwargs)

    def make_revoke(self, event_id=None, user_id=None):
        """Add standard revoke options to the update"""
        if event_id is None:
            event_id = get_event()
        if user_id is None:
            context.session.assertLogin()
            user_id = context.session.user_id
        self.data['revoke_event'] = event_id
        self.data['revoker_id'] = user_id
        self.rawdata['active'] = 'NULL'
        self.clauses.append('active = TRUE')

    def execute(self):
        return _dml(str(self), self.get_values())


class QueryProcessor(object):
    """
    Build a query from its components.
    - columns, aliases, tables: lists of the column names to retrieve,
      the tables to retrieve them from, and the key names to use when
      returning values as a map, respectively
    - joins: a list of joins in the form 'table1 ON table1.col1 = table2.col2', 'JOIN' will be
             prepended automatically; if extended join syntax (LEFT, OUTER, etc.) is required,
             it can be specified, and 'JOIN' will not be prepended
    - clauses: a list of where clauses in the form 'table1.col1 OPER table2.col2-or-variable';
               each clause will be surrounded by parentheses and all will be AND'ed together
    - values: the map that will be used to replace any substitution expressions in the query
    - transform: a function that will be called on each row (not compatible with
                 countOnly or singleValue)
    - opts: a map of query options; currently supported options are:
        countOnly: if True, return an integer indicating how many results would have been
                   returned, rather than the actual query results
        order: a column or alias name to use in the 'ORDER BY' clause
        offset: an integer to use in the 'OFFSET' clause
        limit: an integer to use in the 'LIMIT' clause
        asList: if True, return results as a list of lists, where each list contains the
                column values in query order, rather than the usual list of maps
        rowlock: if True, use "FOR UPDATE" to lock the queried rows
        group: a column or alias name to use in the 'GROUP BY' clause
               (controlled by enable_group)
    - enable_group: if True, opts.group will be enabled
    """

    iterchunksize = 1000

    def __init__(self, columns=None, aliases=None, tables=None,
                 joins=None, clauses=None, values=None, transform=None,
                 opts=None, enable_group=False):
        self.columns = columns
        self.aliases = aliases
        if columns and aliases:
            if len(columns) != len(aliases):
                raise Exception('column and alias lists must be the same length')
            # reorder
            alias_table = sorted(zip(aliases, columns))
            self.aliases = [x[0] for x in alias_table]
            self.columns = [x[1] for x in alias_table]
            self.colsByAlias = dict(alias_table)
        else:
            self.colsByAlias = {}
            if columns:
                self.columns = sorted(columns)
            if aliases:
                self.aliases = sorted(aliases)
        self.tables = tables
        self.joins = joins
        if clauses:
            self.clauses = sorted(clauses)
        else:
            self.clauses = clauses
        self.cursors = 0
        if values:
            self.values = values
        else:
            self.values = {}
        self.transform = transform
        if opts:
            self.opts = opts
        else:
            self.opts = {}
        self.enable_group = enable_group
        self.logger = logging.getLogger('koji.db')

    def countOnly(self, count):
        self.opts['countOnly'] = count

    def __str__(self):
        query = \
            """
SELECT %(col_str)s
  FROM %(table_str)s
%(join_str)s
%(clause_str)s
 %(group_str)s
 %(order_str)s
%(offset_str)s
 %(limit_str)s
"""
        if self.opts.get('countOnly'):
            if self.opts.get('offset') \
                    or self.opts.get('limit') \
                    or (self.enable_group and self.opts.get('group')):
                # If we're counting with an offset and/or limit, we need
                # to wrap the offset/limited query and then count the results,
                # rather than trying to offset/limit the single row returned
                # by count(*).  Because we're wrapping the query, we don't care
                # about the column values.
                col_str = '1'
            else:
                col_str = 'count(*)'
        else:
            col_str = self._seqtostr(self.columns)
        table_str = self._seqtostr(self.tables, sort=True)
        join_str = self._joinstr()
        clause_str = self._seqtostr(self.clauses, sep=')\n   AND (')
        if clause_str:
            clause_str = ' WHERE (' + clause_str + ')'
        if self.enable_group:
            group_str = self._group()
        else:
            group_str = ''
        order_str = self._order()
        offset_str = self._optstr('offset')
        limit_str = self._optstr('limit')

        query = query % locals()
        if self.opts.get('countOnly') and \
            (self.opts.get('offset') or
             self.opts.get('limit') or
             (self.enable_group and self.opts.get('group'))):
            query = 'SELECT count(*)\nFROM (' + query + ') numrows'
        if self.opts.get('rowlock'):
            query += '\n FOR UPDATE'
        return query

    def __repr__(self):
        return '<QueryProcessor: ' \
               'columns=%r, aliases=%r, tables=%r, joins=%r, clauses=%r, values=%r, opts=%r>' % \
               (self.columns, self.aliases, self.tables, self.joins, self.clauses, self.values,
                self.opts)

    def _seqtostr(self, seq, sep=', ', sort=False):
        if seq:
            if sort:
                seq = sorted(seq)
            return sep.join(seq)
        else:
            return ''

    def _joinstr(self):
        if not self.joins:
            return ''
        result = ''
        for join in self.joins:
            if result:
                result += '\n'
            if re.search(r'\bjoin\b', join, re.IGNORECASE):
                # The join clause already contains the word 'join',
                # so don't prepend 'JOIN' to it
                result += '  ' + join
            else:
                result += '  JOIN ' + join
        return result

    def _order(self):
        # Don't bother sorting if we're just counting
        if self.opts.get('countOnly'):
            return ''
        order_opt = self.opts.get('order')
        if order_opt:
            order_exprs = []
            for order in order_opt.split(','):
                if order.startswith('-'):
                    order = order[1:]
                    direction = ' DESC'
                else:
                    direction = ''
                # Check if we're ordering by alias first
                orderCol = self.colsByAlias.get(order)
                if orderCol:
                    pass
                elif order in self.columns:
                    orderCol = order
                else:
                    raise Exception('Invalid order: ' + order)
                order_exprs.append(orderCol + direction)
            return 'ORDER BY ' + ', '.join(order_exprs)
        else:
            return ''

    def _group(self):
        group_opt = self.opts.get('group')
        if group_opt:
            group_exprs = []
            for group in group_opt.split(','):
                if group:
                    group_exprs.append(group)
            return 'GROUP BY ' + ', '.join(group_exprs)
        else:
            return ''

    def _optstr(self, optname):
        optval = self.opts.get(optname)
        if optval:
            return '%s %i' % (optname.upper(), optval)
        else:
            return ''

    def singleValue(self, strict=True):
        # self.transform not applied here
        return _singleValue(str(self), self.values, strict=strict)

    def execute(self):
        query = str(self)
        if self.opts.get('countOnly'):
            return _singleValue(query, self.values, strict=True)
        elif self.opts.get('asList'):
            if self.transform is None:
                return _fetchMulti(query, self.values)
            else:
                # if we're transforming, generate the dicts so the transform can modify
                fields = self.aliases or self.columns
                data = _multiRow(query, self.values, fields)
                data = [self.transform(row) for row in data]
                # and then convert back to lists
                data = [[row[f] for f in fields] for row in data]
                return data
        else:
            data = _multiRow(query, self.values, (self.aliases or self.columns))
            if self.transform is not None:
                data = [self.transform(row) for row in data]
            return data

    def iterate(self):
        if self.opts.get('countOnly'):
            return self.execute()
        elif self.opts.get('limit') and self.opts['limit'] < self.iterchunksize:
            return self.execute()
        else:
            fields = self.aliases or self.columns
            fields = list(fields)
            cname = "qp_cursor_%s_%i_%i" % (id(self), os.getpid(), self.cursors)
            self.cursors += 1
            self.logger.debug('Setting up query iterator. cname=%r', cname)
            return self._iterate(cname, str(self), self.values.copy(), fields,
                                 self.iterchunksize, self.opts.get('asList'))

    def _iterate(self, cname, query, values, fields, chunksize, as_list=False):
        # We pass all this data into the generator so that the iterator works
        # from the snapshot when it was generated. Otherwise reuse of the processor
        # for similar queries could have unpredictable results.
        query = "DECLARE %s NO SCROLL CURSOR FOR %s" % (cname, query)
        c = context.cnx.cursor()
        c.execute(query, values)
        c.close()
        try:
            query = "FETCH %i FROM %s" % (chunksize, cname)
            while True:
                if as_list:
                    if self.transform is None:
                        buf = _fetchMulti(query, {})
                    else:
                        # if we're transforming, generate the dicts so the transform can modify
                        buf = _multiRow(query, self.values, fields)
                        buf = [self.transform(row) for row in buf]
                        # and then convert back to lists
                        buf = [[row[f] for f in fields] for row in buf]
                else:
                    buf = _multiRow(query, {}, fields)
                    if self.transform is not None:
                        buf = [self.transform(row) for row in buf]
                if not buf:
                    break
                for row in buf:
                    yield row
        finally:
            c = context.cnx.cursor()
            c.execute("CLOSE %s" % cname)
            c.close()

    def executeOne(self, strict=False):
        results = self.execute()
        if isinstance(results, list):
            if len(results) > 0:
                if strict and len(results) > 1:
                    raise koji.GenericError('multiple rows returned for a single row query')
                return results[0]
            elif strict:
                raise koji.GenericError('query returned no rows')
            else:
                return None
        return results


class BulkInsertProcessor(object):
    def __init__(self, table, data=None, columns=None, strict=True, batch=1000):
        """Do bulk inserts - it has some limitations compared to
        InsertProcessor (no rawset, dup_check).

        set() is replaced with add_record() to avoid confusion

        table   - name of the table
        data    - list of dict per record
        columns - list/set of names of used columns - makes sense
                  mainly with strict=True
        strict  - if True, all records must contain values for all columns.
                  if False, missing values will be inserted as NULLs
        batch   - batch size for inserts (one statement per batch)
        """

        self.table = table
        self.data = []
        if columns is None:
            self.columns = set()
        else:
            self.columns = set(columns)
        if data is not None:
            self.data = data
            for row in data:
                self.columns |= set(row.keys())
        self.strict = strict
        self.batch = batch

    def __str__(self):
        if not self.data:
            return "-- incomplete insert: no data"
        query, params = self._get_insert(self.data)
        return query

    def _get_insert(self, data):
        """
        Generate one insert statement for the given data

        :param list data: list of rows (dict format) to insert
        :returns: (query, params)
        """

        if not data:
            # should not happen
            raise ValueError('no data for insert')
        parts = ['INSERT INTO %s ' % self.table]
        columns = sorted(self.columns)
        parts.append("(%s) " % ', '.join(columns))

        prepared_data = {}
        values = []
        i = 0
        for row in data:
            row_values = []
            for key in columns:
                if key in row:
                    row_key = '%s%d' % (key, i)
                    row_values.append("%%(%s)s" % row_key)
                    prepared_data[row_key] = row[key]
                elif self.strict:
                    raise koji.GenericError("Missing value %s in BulkInsert" % key)
                else:
                    row_values.append("NULL")
            values.append("(%s)" % ', '.join(row_values))
            i += 1
        parts.append("VALUES %s" % ', '.join(values))
        return ''.join(parts), prepared_data

    def __repr__(self):
        return "<BulkInsertProcessor: %r>" % vars(self)

    def add_record(self, **kwargs):
        """Set whole record via keyword args"""
        if not kwargs:
            raise koji.GenericError("Missing values in BulkInsert.add_record")
        self.data.append(kwargs)
        self.columns |= set(kwargs.keys())

    def execute(self):
        if not self.batch:
            self._one_insert(self.data)
        else:
            for i in range(0, len(self.data), self.batch):
                data = self.data[i:i + self.batch]
                self._one_insert(data)

    def _one_insert(self, data):
        query, params = self._get_insert(data)
        _dml(query, params)


def _applyQueryOpts(results, queryOpts):
    """
    Apply queryOpts to results in the same way QueryProcessor would.
    results is a list of maps.
    queryOpts is a map which may contain the following fields:
      countOnly
      order
      offset
      limit

    Note:
    - asList is supported by QueryProcessor but not by this method.
    We don't know the original query order, and so don't have a way to
    return a useful list.  asList should be handled by the caller.
    - group is supported by QueryProcessor but not by this method as well.
    """
    if queryOpts is None:
        queryOpts = {}
    if queryOpts.get('order'):
        order = queryOpts['order']
        reverse = False
        if order.startswith('-'):
            order = order[1:]
            reverse = True
        results.sort(key=lambda o: o[order], reverse=reverse)
    if queryOpts.get('offset'):
        results = results[queryOpts['offset']:]
    if queryOpts.get('limit'):
        results = results[:queryOpts['limit']]
    if queryOpts.get('countOnly'):
        return len(results)
    else:
        return results
