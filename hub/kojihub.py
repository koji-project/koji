# Python library

# kojihub - library for koji's XMLRPC interface
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
#       Mike Bonnet <mikeb@redhat.com>
#       Cristian Balint <cbalint@redhat.com>

from __future__ import absolute_import

import base64
import calendar
import datetime
import errno
import fcntl
import fnmatch
import functools
import hashlib
import json
import logging
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import time
import traceback
from urllib.parse import parse_qs
import xmlrpc.client
import zipfile

import rpm

import koji
import koji.auth
import koji.db
import koji.plugin
import koji.policy
import koji.rpmdiff
import koji.tasks
import koji.xmlrpcplus
from koji.context import context
from koji.daemon import SCM
from koji.util import (
    base64encode,
    decode_bytes,
    dslice,
    joinpath,
    md5_constructor,
    move_and_symlink,
    multi_fnmatch,
    safer_move,
    to_list
)

try:
    # py 3.6+
    import secrets
except ImportError:
    import random
    secrets = None


logger = logging.getLogger('koji.hub')


NUMERIC_TYPES = (int, float)


def log_error(msg):
    logger.error(msg)


def xform_user_krb(entry):
    entry['krb_principals'] = [x for x in entry['krb_principals'] if x is not None]
    return entry


class Task(object):
    """A task for the build hosts"""

    fields = (
        ('task.id', 'id'),
        ('task.state', 'state'),
        ('task.create_time', 'create_time'),
        ('EXTRACT(EPOCH FROM create_time)', 'create_ts'),
        ('task.start_time', 'start_time'),
        ('EXTRACT(EPOCH FROM task.start_time)', 'start_ts'),
        ('task.completion_time', 'completion_time'),
        ('EXTRACT(EPOCH FROM completion_time)', 'completion_ts'),
        ('task.channel_id', 'channel_id'),
        ('task.host_id', 'host_id'),
        ('task.parent', 'parent'),
        ('task.label', 'label'),
        ('task.waiting', 'waiting'),
        ('task.awaited', 'awaited'),
        ('task.owner', 'owner'),
        ('task.method', 'method'),
        ('task.arch', 'arch'),
        ('task.priority', 'priority'),
        ('task.weight', 'weight'))

    def __init__(self, id):
        self.id = id
        self.logger = logging.getLogger("koji.hub.Task")

    def _split_fields(self, fields=None):
        """Helper function for split fields to QueryProcessor's
       columns/aliases options"""
        if fields is None:
            fields = self.fields
        columns = [f[0] for f in fields]
        aliases = [f[1] for f in fields]
        return columns, aliases

    def verifyHost(self, host_id=None):
        """Verify that host owns task"""
        if host_id is None:
            host_id = context.session.host_id
        if host_id is None:
            return False
        task_id = self.id
        # getting a row lock on this task to ensure task assignment sanity
        # no other concurrent transaction should be altering this row
        q = """SELECT state,host_id FROM task WHERE id=%(task_id)s FOR UPDATE"""
        r = _fetchSingle(q, locals())
        if not r:
            raise koji.GenericError("No such task: %i" % task_id)
        state, otherhost = r
        return (state == koji.TASK_STATES['OPEN'] and otherhost == host_id)

    def assertHost(self, host_id):
        if not self.verifyHost(host_id):
            raise koji.ActionNotAllowed("host %d does not own task %d" % (host_id, self.id))

    def getOwner(self):
        """Return the owner (user_id) for this task"""
        q = """SELECT owner FROM task WHERE id=%(id)i"""
        return _singleValue(q, vars(self))

    def verifyOwner(self, user_id=None):
        """Verify that user owns task"""
        if user_id is None:
            user_id = context.session.user_id
        if user_id is None:
            return False
        task_id = self.id
        # getting a row lock on this task to ensure task state sanity
        q = """SELECT owner FROM task WHERE id=%(task_id)s FOR UPDATE"""
        r = _fetchSingle(q, locals())
        if not r:
            raise koji.GenericError("No such task: %i" % task_id)
        (owner,) = r
        return (owner == user_id)

    def assertOwner(self, user_id=None):
        if not self.verifyOwner(user_id):
            raise koji.ActionNotAllowed("user %d does not own task %d" % (user_id, self.id))

    def lock(self, host_id, newstate='OPEN', force=False):
        """Attempt to associate the task for host, either to assign or open

        returns True if successful, False otherwise"""
        info = self.getInfo(request=True)
        self.runCallbacks('preTaskStateChange', info, 'state', koji.TASK_STATES[newstate])
        self.runCallbacks('preTaskStateChange', info, 'host_id', host_id)
        # we use row-level locks to keep things sane
        # note the SELECT...FOR UPDATE
        task_id = self.id
        if not force:
            q = """SELECT state,host_id FROM task WHERE id=%(task_id)i FOR UPDATE"""
            r = _fetchSingle(q, locals())
            if not r:
                raise koji.GenericError("No such task: %i" % task_id)
            state, otherhost = r
            if state == koji.TASK_STATES['FREE']:
                if otherhost is not None:
                    log_error("Error: task %i is both free and locked (host %i)"
                              % (task_id, otherhost))
                    return False
            elif state == koji.TASK_STATES['ASSIGNED']:
                if otherhost is None:
                    log_error("Error: task %i is assigned, but has no assignee"
                              % (task_id))
                    return False
                elif otherhost != host_id:
                    # task is assigned to someone else
                    return False
                # otherwise the task is assigned to host_id, so keep going
            else:
                if otherhost is None:
                    log_error("Error: task %i is non-free but unlocked (state %i)"
                              % (task_id, state))
                return False
        # if we reach here, task is either
        #  - free and unlocked
        #  - assigned to host_id
        #  - force option is enabled
        state = koji.TASK_STATES[newstate]
        update = UpdateProcessor('task', clauses=['id=%(task_id)i'], values=locals())
        update.set(state=state, host_id=host_id)
        if state == koji.TASK_STATES['OPEN']:
            update.rawset(start_time='NOW()')
        update.execute()
        self.runCallbacks('postTaskStateChange', info, 'state', koji.TASK_STATES[newstate])
        self.runCallbacks('postTaskStateChange', info, 'host_id', host_id)
        return True

    def assign(self, host_id, force=False):
        """Attempt to assign the task to host.

        returns True if successful, False otherwise"""
        return self.lock(host_id, 'ASSIGNED', force)

    def open(self, host_id):
        """Attempt to open the task for host.

        returns task data if successful, None otherwise"""
        if self.lock(host_id, 'OPEN'):
            # get more complete data to return
            fields = self.fields + (('task.request', 'request'),)
            query = QueryProcessor(tables=['task'], clauses=['id=%(id)i'], values=vars(self),
                                   columns=[f[0] for f in fields], aliases=[f[1] for f in fields])
            ret = query.executeOne()
            if ret['request'].find('<?xml', 0, 10) == -1:
                # handle older base64 encoded data
                data = base64.b64decode(ret['request'])
                # we can't return raw bytes and this /should/ be a valid string
                ret['request'] = decode_bytes(data)
            return ret
        else:
            return None

    def free(self):
        """Free a task"""
        info = self.getInfo(request=True)
        self.runCallbacks('preTaskStateChange', info, 'state', koji.TASK_STATES['FREE'])
        self.runCallbacks('preTaskStateChange', info, 'host_id', None)
        task_id = self.id
        # access checks should be performed by calling function
        query = """SELECT state FROM task WHERE id = %(id)i FOR UPDATE"""
        row = _fetchSingle(query, vars(self))
        if not row:
            raise koji.GenericError("No such task: %i" % self.id)
        oldstate = row[0]
        if koji.TASK_STATES[oldstate] in ['CLOSED', 'CANCELED', 'FAILED']:
            raise koji.GenericError("Cannot free task %i, state is %s" %
                                    (self.id, koji.TASK_STATES[oldstate]))
        newstate = koji.TASK_STATES['FREE']
        newhost = None
        q = """UPDATE task SET state=%(newstate)s,host_id=%(newhost)s
        WHERE id=%(task_id)s"""
        _dml(q, locals())
        self.runCallbacks('postTaskStateChange', info, 'state', koji.TASK_STATES['FREE'])
        self.runCallbacks('postTaskStateChange', info, 'host_id', None)
        return True

    def setWeight(self, weight):
        """Set weight for task"""
        task_id = self.id
        weight = float(weight)
        info = self.getInfo(request=True)
        self.runCallbacks('preTaskStateChange', info, 'weight', weight)
        # access checks should be performed by calling function
        q = """UPDATE task SET weight=%(weight)s WHERE id = %(task_id)s"""
        _dml(q, locals())
        self.runCallbacks('postTaskStateChange', info, 'weight', weight)

    def setPriority(self, priority, recurse=False):
        """Set priority for task"""
        task_id = self.id
        priority = int(priority)
        info = self.getInfo(request=True)
        self.runCallbacks('preTaskStateChange', info, 'priority', priority)
        # access checks should be performed by calling function
        q = """UPDATE task SET priority=%(priority)s WHERE id = %(task_id)s"""
        _dml(q, locals())
        self.runCallbacks('postTaskStateChange', info, 'priority', priority)

        if recurse:
            # Change priority of child tasks
            q = """SELECT id FROM task WHERE parent = %(task_id)s"""
            for (child_id,) in _fetchMulti(q, locals()):
                Task(child_id).setPriority(priority, recurse=True)

    def _close(self, result, state):
        """Mark task closed and set response

        Returns True if successful, False if not"""
        task_id = self.id
        # access checks should be performed by calling function
        # this is an approximation, and will be different than what is in the database
        # the actual value should be retrieved from the 'new' value of the post callback
        now = time.time()
        info = self.getInfo(request=True)
        info['result'] = result
        self.runCallbacks('preTaskStateChange', info, 'state', state)
        self.runCallbacks('preTaskStateChange', info, 'completion_ts', now)
        update = """UPDATE task SET result = %(result)s, state = %(state)s, completion_time = NOW()
        WHERE id = %(task_id)d
        """
        # get the result from the info dict, so callbacks have a chance to modify it
        _dml(update, {'result': info['result'], 'state': state, 'task_id': task_id})
        self.runCallbacks('postTaskStateChange', info, 'state', state)
        self.runCallbacks('postTaskStateChange', info, 'completion_ts', now)

    def close(self, result):
        # access checks should be performed by calling function
        self._close(result, koji.TASK_STATES['CLOSED'])

    def fail(self, result):
        # access checks should be performed by calling function
        self._close(result, koji.TASK_STATES['FAILED'])

    def getState(self):
        query = """SELECT state FROM task WHERE id = %(id)i"""
        return _singleValue(query, vars(self))

    def isFinished(self):
        return (koji.TASK_STATES[self.getState()] in ['CLOSED', 'CANCELED', 'FAILED'])

    def isCanceled(self):
        return (self.getState() == koji.TASK_STATES['CANCELED'])

    def isFailed(self):
        return (self.getState() == koji.TASK_STATES['FAILED'])

    def cancel(self, recurse=True):
        """Cancel this task.

        A task can only be canceled if it is not already in the 'CLOSED' state.
        If it is, no action will be taken.  Return True if the task is
        successfully canceled, or if it was already canceled, False if it is
        closed."""
        # access checks should be performed by calling function
        now = time.time()
        info = self.getInfo(request=True)
        self.runCallbacks('preTaskStateChange', info, 'state', koji.TASK_STATES['CANCELED'])
        self.runCallbacks('preTaskStateChange', info, 'completion_ts', now)
        task_id = self.id
        q = """SELECT state FROM task WHERE id = %(task_id)s FOR UPDATE"""
        state = _singleValue(q, locals())
        st_canceled = koji.TASK_STATES['CANCELED']
        st_closed = koji.TASK_STATES['CLOSED']
        st_failed = koji.TASK_STATES['FAILED']
        if state == st_canceled:
            return True
        elif state in [st_closed, st_failed]:
            return False
        update = """UPDATE task SET state = %(st_canceled)i, completion_time = NOW()
        WHERE id = %(task_id)i"""
        _dml(update, locals())
        self.runCallbacks('postTaskStateChange', info, 'state', koji.TASK_STATES['CANCELED'])
        self.runCallbacks('postTaskStateChange', info, 'completion_ts', now)
        # cancel associated builds (only if state is 'BUILDING')
        # since we check build state, we avoid loops with cancel_build on our end
        b_building = koji.BUILD_STATES['BUILDING']
        q = """SELECT id FROM build WHERE task_id = %(task_id)i
        AND state = %(b_building)i
        FOR UPDATE"""
        for (build_id,) in _fetchMulti(q, locals()):
            cancel_build(build_id, cancel_task=False)
        if recurse:
            # also cancel child tasks
            self.cancelChildren()
        return True

    def cancelChildren(self):
        """Cancel child tasks"""
        task_id = self.id
        q = """SELECT id FROM task WHERE parent = %(task_id)i"""
        for (id,) in _fetchMulti(q, locals()):
            Task(id).cancel(recurse=True)

    def cancelFull(self, strict=True):
        """Cancel this task and every other task in its group

        If strict is true, then this must be a top-level task
        Otherwise we will follow up the chain to find the top-level task
        """
        task_id = self.id
        q = """SELECT parent FROM task WHERE id = %(task_id)i FOR UPDATE"""
        parent = _singleValue(q, locals())
        if parent is not None:
            if strict:
                raise koji.GenericError("Task %d is not top-level (parent=%d)" % (task_id, parent))
            # otherwise, find the top-level task and go from there
            seen = {task_id: 1}
            while parent is not None:
                if parent in seen:
                    raise koji.GenericError("Task LOOP at task %i" % task_id)
                task_id = parent
                seen[task_id] = 1
                parent = _singleValue(q, locals())
            return Task(task_id).cancelFull(strict=True)
        # We handle the recursion ourselves, since self.cancel will stop at
        # canceled or closed tasks.
        tasklist = [task_id]
        seen = {}
        # query for use in loop
        q_children = """SELECT id FROM task WHERE parent = %(task_id)i"""
        for task_id in tasklist:
            if task_id in seen:
                # shouldn't happen
                raise koji.GenericError("Task LOOP at task %i" % task_id)
            seen[task_id] = 1
            Task(task_id).cancel(recurse=False)
            for (child_id,) in _fetchMulti(q_children, locals()):
                tasklist.append(child_id)

    def getRequest(self):
        query = QueryProcessor(columns=['request'], tables=['task'],
                               clauses=['id = %(id)i'], values={'id': self.id})
        xml_request = query.singleValue()
        if xml_request.find('<?xml', 0, 10) == -1:
            # handle older base64 encoded data
            xml_request = base64.b64decode(xml_request)
        # note: loads accepts either bytes or string
        params, method = xmlrpc.client.loads(xml_request)
        return params

    def getResult(self, raise_fault=True):
        query = """SELECT state,result FROM task WHERE id = %(id)i"""
        r = _fetchSingle(query, vars(self))
        if not r:
            raise koji.GenericError("No such task")
        state, xml_result = r
        if koji.TASK_STATES[state] == 'CANCELED':
            raise koji.GenericError("Task %i is canceled" % self.id)
        elif koji.TASK_STATES[state] not in ['CLOSED', 'FAILED']:
            raise koji.GenericError("Task %i is not finished" % self.id)
        if xml_result.find('<?xml', 0, 10) == -1:
            # handle older base64 encoded data
            xml_result = base64.b64decode(xml_result)
        try:
            # If the result is a Fault, then loads will raise it
            # This is normally what we want to happen
            result, method = xmlrpc.client.loads(xml_result)
        except xmlrpc.client.Fault as fault:
            if raise_fault:
                raise
            # Note that you can't really return a fault over xmlrpc, except by
            # raising it. We return a dictionary in the same format that
            # multiCall does.
            return {'faultCode': fault.faultCode, 'faultString': fault.faultString}
        return result[0]

    def getInfo(self, strict=True, request=False):
        """Return information about the task in a dictionary.  If "request" is True,
        the request will be decoded and included in the dictionary."""
        columns, aliases = self._split_fields()
        query = QueryProcessor(columns=columns, aliases=aliases,
                               tables=['task'], clauses=['id = %(id)i'],
                               values={'id': self.id})
        result = query.executeOne(strict=strict)
        if result and request:
            result['request'] = self.getRequest()
        return result

    def getChildren(self, request=False):
        """Return information about tasks with this task as their
        parent.  If there are no such Tasks, return an empty list."""
        fields = self.fields
        if request:
            fields = fields + (('request', 'request'),)
        columns, aliases = self._split_fields(fields)
        query = QueryProcessor(columns=columns, aliases=aliases,
                               tables=['task'], clauses=['parent = %(id)i'],
                               values={'id': self.id})
        results = query.execute()
        if request:
            for task in results:
                if task['request'].find('<?xml', 0, 10) == -1:
                    # handle older base64 encoded data
                    task['request'] = base64.b64decode(task['request'])
                # note: loads accepts either bytes or string
                task['request'] = xmlrpc.client.loads(task['request'])[0]
        return results

    def runCallbacks(self, cbtype, old_info, attr, new_val):
        if cbtype.startswith('pre'):
            info = old_info
        elif cbtype.startswith('post'):
            info = self.getInfo(request=True)
            if info['state'] == koji.TASK_STATES['CLOSED']:
                # if task is closed, include the result as well
                info['result'] = self.getResult()
            new_val = info[attr]
        else:
            raise koji.GenericError('unknown callback type: %s' % cbtype)
        old_val = old_info[attr]
        if attr == 'state':
            # state is passed in as an integer, but we want to use the string
            old_val = koji.TASK_STATES[old_val]
            new_val = koji.TASK_STATES[new_val]
        koji.plugin.run_callbacks(cbtype, attribute=attr, old=old_val, new=new_val,
                                  info=info)


def make_task(method, arglist, **opts):
    """Create a task

    This call should not be directly exposed via xmlrpc
    Optional args:
        parent: the id of the parent task (creates a subtask)
        label: (subtasks only) the label of the subtask
        owner: the user_id that should own the task
        channel: the channel to place the task in
        arch: the arch for the task
        priority: the priority of the task
        assign: a host_id to assign the task to
    """
    if 'parent' in opts:
        # for subtasks, we use some of the parent's options as defaults
        fields = ('state', 'owner', 'channel_id', 'priority', 'arch')
        q = """SELECT %s FROM task WHERE id = %%(parent)i""" % ','.join(fields)
        r = _fetchSingle(q, opts)
        if not r:
            raise koji.GenericError("Invalid parent task: %(parent)s" % opts)
        pdata = dict(zip(fields, r))
        if pdata['state'] != koji.TASK_STATES['OPEN']:
            raise koji.GenericError("Parent task (id %(parent)s) is not open" % opts)
        # default to a higher priority than parent
        opts.setdefault('priority', pdata['priority'] - 1)
        for f in ('owner', 'arch'):
            opts.setdefault(f, pdata[f])
        opts.setdefault('label', None)
    else:
        opts.setdefault('priority', koji.PRIO_DEFAULT)
        # calling function should enforce priority limitations, if applicable
        opts.setdefault('arch', 'noarch')
        if not context.session.logged_in:
            raise koji.GenericError('task must have an owner')
        else:
            opts['owner'] = context.session.user_id
        opts['label'] = None
        opts['parent'] = None
    # determine channel from policy
    policy_data = {}
    policy_data['method'] = method
    for key in 'arch', 'parent', 'label', 'owner':
        policy_data[key] = opts[key]
    policy_data['user_id'] = opts['owner']
    if 'channel' in opts:
        policy_data['req_channel'] = opts['channel']
        req_channel_id = get_channel_id(opts['channel'], strict=True)
    policy_data.update(policy_data_from_task_args(method, arglist))

    ruleset = context.policy.get('channel')
    result = ruleset.apply(policy_data)
    if result is None:
        logger.warning('Channel policy returned no result, using default')
        opts['channel_id'] = get_channel_id('default', strict=True)
    else:
        try:
            parts = result.split()
            if parts[0] == "use":
                opts['channel_id'] = get_channel_id(parts[1], strict=True)
            elif parts[0] == "parent":
                if not opts.get('parent'):
                    logger.error("Invalid channel policy result (no parent task): %s",
                                 ruleset.last_rule())
                    raise koji.GenericError("invalid channel policy")
                opts['channel_id'] = pdata['channel_id']
            elif parts[0] == "req":
                if 'channel' not in opts:
                    logger.error('Invalid channel policy result (no channel requested): %s',
                                 ruleset.last_rule())
                    raise koji.GenericError("invalid channel policy")
                opts['channel_id'] = req_channel_id
            else:
                logger.error("Invalid result from channel policy: %s", ruleset.last_rule())
                raise koji.GenericError("invalid channel policy")
        except IndexError:
            logger.error("Invalid result from channel policy: %s", ruleset.last_rule())
            raise koji.GenericError("invalid channel policy")

    # encode xmlrpc request
    opts['request'] = koji.xmlrpcplus.dumps(tuple(arglist), methodname=method)
    opts['state'] = koji.TASK_STATES['FREE']
    opts['method'] = method
    koji.plugin.run_callbacks(
        'preTaskStateChange', attribute='state', old=None, new='FREE', info=opts)
    # stick it in the database

    idata = dslice(opts, ['state', 'owner', 'method', 'request', 'priority', 'parent', 'label',
                          'channel_id', 'arch'])
    if opts.get('assign'):
        idata['state'] = koji.TASK_STATES['ASSIGNED']
        idata['host_id'] = opts['assign']
    insert = InsertProcessor('task', data=idata)
    insert.execute()
    task_id = _singleValue("SELECT currval('task_id_seq')", strict=True)
    opts['id'] = task_id
    koji.plugin.run_callbacks(
        'postTaskStateChange', attribute='state', old=None, new='FREE', info=opts)
    return task_id


def eventCondition(event, table=None):
    """return the proper WHERE condition to select data at the time specified by event. """
    if not table:
        table = ''
    else:
        table += '.'
    if event is None:
        return """(%(table)sactive = TRUE)""" % locals()
    elif isinstance(event, int):
        return "(%(table)screate_event <= %(event)d AND ( %(table)srevoke_event IS NULL OR " \
               "%(event)d < %(table)srevoke_event ))" % locals()
    else:
        raise koji.GenericError("Invalid event: %r" % event)


def readGlobalInheritance(event=None):
    c = context.cnx.cursor()
    fields = ('tag_id', 'parent_id', 'name', 'priority', 'maxdepth', 'intransitive',
              'noconfig', 'pkg_filter')
    q = """SELECT %s FROM tag_inheritance JOIN tag ON parent_id = id
    WHERE %s
    ORDER BY priority
    """ % (",".join(fields), eventCondition(event))
    c.execute(q, locals())
    # convert list of lists into a list of dictionaries
    return [dict(zip(fields, x)) for x in c.fetchall()]


def readInheritanceData(tag_id, event=None):
    c = context.cnx.cursor()
    fields = ('parent_id', 'name', 'priority', 'maxdepth', 'intransitive', 'noconfig',
              'pkg_filter')
    q = """SELECT %s FROM tag_inheritance JOIN tag ON parent_id = id
    WHERE %s AND tag_id = %%(tag_id)i
    ORDER BY priority
    """ % (",".join(fields), eventCondition(event))
    c.execute(q, locals())
    # convert list of lists into a list of dictionaries
    data = [dict(zip(fields, x)) for x in c.fetchall()]
    # include the current tag_id as child_id, so we can retrace the inheritance chain later
    for datum in data:
        datum['child_id'] = tag_id
    return data


def readDescendantsData(tag_id, event=None):
    c = context.cnx.cursor()
    fields = ('tag_id', 'parent_id', 'name', 'priority', 'maxdepth', 'intransitive', 'noconfig',
              'pkg_filter')
    q = """SELECT %s FROM tag_inheritance JOIN tag ON tag_id = id
    WHERE %s AND parent_id = %%(tag_id)i
    ORDER BY priority
    """ % (",".join(fields), eventCondition(event))
    c.execute(q, locals())
    # convert list of lists into a list of dictionaries
    data = [dict(zip(fields, x)) for x in c.fetchall()]
    return data


def writeInheritanceData(tag_id, changes, clear=False):
    """Add or change inheritance data for a tag"""
    context.session.assertPerm('tag')
    _writeInheritanceData(tag_id, changes, clear)


def _writeInheritanceData(tag_id, changes, clear=False):
    """Add or change inheritance data for a tag"""
    fields = ('parent_id', 'priority', 'maxdepth', 'intransitive', 'noconfig', 'pkg_filter')
    if isinstance(changes, dict):
        changes = [changes]
    # duplicated parent_id should not be contained in changes
    parent_ids = set()
    for link in changes:
        check_fields = fields
        if link.get('delete link'):
            check_fields = ('parent_id',)
        for f in check_fields:
            if f not in link:
                raise koji.GenericError("No value for %s" % f)
        parent_id = link['parent_id']
        if parent_id in parent_ids:
            raise koji.GenericError("Changes should not contain duplicated"
                                    " parent_id(%i)" % parent_id)
        else:
            parent_ids.add(parent_id)
        # check existence of parent
        get_tag(parent_id, strict=True)
    # read current data and index
    data = dict([[link['parent_id'], link] for link in readInheritanceData(tag_id)])
    for link in changes:
        link['is_update'] = True
        parent_id = link['parent_id']
        orig = data.get(parent_id)
        if link.get('delete link'):
            if orig:
                data[parent_id] = link
        elif not orig or clear:
            data[parent_id] = link
        else:
            # not a delete request and we have a previous link to parent
            for f in fields:
                if orig[f] != link[f]:
                    data[parent_id] = link
                    break
    if clear:
        for link in data.values():
            if not link.get('is_update'):
                link['delete link'] = True
                link['is_update'] = True
    changed = False
    for link in data.values():
        if link.get('is_update'):
            changed = True
            break
    if not changed:
        # nothing to do
        log_error("No inheritance changes")
        return
    # check for duplicate priorities
    pri_index = {}
    for link in data.values():
        if link.get('delete link'):
            continue
        pri_index.setdefault(link['priority'], []).append(link)
    for pri, dups in pri_index.items():
        if len(dups) <= 1:
            continue
        # oops, duplicate entries for a single priority
        dup_ids = [link['parent_id'] for link in dups]
        raise koji.GenericError("Inheritance priorities must be unique (pri %s: %r )" %
                                (pri, dup_ids))
    for parent_id, link in data.items():
        if not link.get('is_update'):
            continue
        # revoke old values
        update = UpdateProcessor('tag_inheritance', values=locals(),
                                 clauses=['tag_id=%(tag_id)s', 'parent_id = %(parent_id)s'])
        update.make_revoke()
        update.execute()
    for parent_id, link in data.items():
        if not link.get('is_update'):
            continue
        # skip rest if we are just deleting
        if link.get('delete link'):
            continue
        # insert new value
        newlink = dslice(link, fields)
        newlink['tag_id'] = tag_id
        # defaults ok for the rest
        insert = InsertProcessor('tag_inheritance', data=newlink)
        insert.make_create()
        insert.execute()


def readFullInheritance(tag_id, event=None, reverse=False, stops=None, jumps=None):
    """Returns a list representing the full, ordered inheritance from tag"""
    if stops is None:
        stops = {}
    if jumps is None:
        jumps = {}
    order = []
    readFullInheritanceRecurse(tag_id, event, order, stops, {}, {}, 0, None, False, [], reverse,
                               jumps)
    return order


def readFullInheritanceRecurse(tag_id, event, order, prunes, top, hist, currdepth, maxdepth,
                               noconfig, pfilter, reverse, jumps):
    if maxdepth is not None and maxdepth < 1:
        return
    # note: maxdepth is relative to where we are, but currdepth is absolute from
    # the top.
    currdepth += 1
    top = top.copy()
    top[tag_id] = 1
    if reverse:
        node = readDescendantsData(tag_id, event)
    else:
        node = readInheritanceData(tag_id, event)
    for link in node:
        if reverse:
            id = link['tag_id']
        else:
            id = link['parent_id']
        if id in jumps:
            id = jumps[id]
        if id in top:
            # LOOP!
            if event is None:
                # only log if the issue is current
                log_error("Warning: INHERITANCE LOOP detected at %s -> %s, pruning" % (tag_id, id))
            # auto prune
            continue
        if id in prunes:
            # ignore pruned tags
            continue
        if link['intransitive'] and len(top) > 1 and not reverse:
            # ignore intransitive inheritance links, except at root
            continue
        if link['priority'] < 0:
            # negative priority indicates pruning, rather than inheritance
            prunes[id] = 1
            continue
        if reverse:
            # maxdepth logic is different in this case. no propagation
            if link['maxdepth'] is not None and link['maxdepth'] < currdepth - 1:
                continue
            nextdepth = None
        else:
            # propagate maxdepth
            nextdepth = link['maxdepth']
            if nextdepth is None:
                if maxdepth is not None:
                    nextdepth = maxdepth - 1
            elif maxdepth is not None:
                nextdepth = min(nextdepth, maxdepth) - 1
        link['nextdepth'] = nextdepth
        link['currdepth'] = currdepth
        # propagate noconfig and pkg_filter controls
        if link['noconfig']:
            noconfig = True
        filter = list(pfilter)  # copy
        pattern = link['pkg_filter']
        if pattern:
            filter.append(pattern)
        link['filter'] = filter
        # check history to avoid redundant entries
        if id in hist:
            # already been there
            # BUT, options may have been different
            rescan = True
            # since rescans are possible, we might have to consider more than one previous hit
            for previous in hist[id]:
                sufficient = True       # is previous sufficient?
                # if last depth was less than current, then previous insufficient
                lastdepth = previous['nextdepth']
                if nextdepth is None:
                    if lastdepth is not None:
                        sufficient = False
                elif lastdepth is not None and lastdepth < nextdepth:
                    sufficient = False
                # if noconfig was on before, but not now, then insuffient
                if previous['noconfig'] and not noconfig:
                    sufficient = False
                # if we had a filter before, then insufficient
                if len(previous['filter']) > 0:
                    # FIXME - we could probably be a little more precise here
                    sufficient = False
                if sufficient:
                    rescan = False
            if not rescan:
                continue
        else:
            hist[id] = []
        hist[id].append(link)  # record history
        order.append(link)
        if link['intransitive'] and reverse:
            # add link, but don't follow it
            continue
        readFullInheritanceRecurse(id, event, order, prunes, top, hist, currdepth, nextdepth,
                                   noconfig, filter, reverse, jumps)

# tag-package operations
#       add
#       remove
#       block
#       unblock
#       change owner
#       list


def _pkglist_remove(tag_id, pkg_id):
    clauses = ('package_id=%(pkg_id)i', 'tag_id=%(tag_id)i')
    update = UpdateProcessor('tag_packages', values=locals(), clauses=clauses)
    update.make_revoke()  # XXX user_id?
    update.execute()


def _pkglist_owner_remove(tag_id, pkg_id):
    clauses = ('package_id=%(pkg_id)i', 'tag_id=%(tag_id)i')
    update = UpdateProcessor('tag_package_owners', values=locals(), clauses=clauses)
    update.make_revoke()  # XXX user_id?
    update.execute()


def _pkglist_owner_add(tag_id, pkg_id, owner):
    _pkglist_owner_remove(tag_id, pkg_id)
    data = {'tag_id': tag_id, 'package_id': pkg_id, 'owner': owner}
    insert = InsertProcessor('tag_package_owners', data=data)
    insert.make_create()  # XXX user_id?
    insert.execute()


def _pkglist_add(tag_id, pkg_id, owner, block, extra_arches):
    # revoke old entry (if present)
    _pkglist_remove(tag_id, pkg_id)
    data = {
        'tag_id': tag_id,
        'package_id': pkg_id,
        'blocked': block,
        'extra_arches': koji.parse_arches(extra_arches, strict=True, allow_none=True)
    }
    insert = InsertProcessor('tag_packages', data=data)
    insert.make_create()  # XXX user_id?
    insert.execute()
    _pkglist_owner_add(tag_id, pkg_id, owner)


def pkglist_add(taginfo, pkginfo, owner=None, block=None, extra_arches=None, force=False,
                update=False):
    """Add to (or update) package list for tag"""
    return _direct_pkglist_add(taginfo, pkginfo, owner, block, extra_arches,
                               force, update, policy=True)


def _direct_pkglist_add(taginfo, pkginfo, owner, block, extra_arches, force,
                        update, policy=False):
    """Like pkglist_add, but without policy or access check"""
    # access control comes a little later (via an assert_policy)
    # should not make any changes until after policy is checked
    tag = get_tag(taginfo, strict=True)
    tag_id = tag['id']
    pkg = lookup_package(pkginfo, strict=False)
    if not pkg:
        if not isinstance(pkginfo, str):
            raise koji.GenericError("Invalid package: %s" % pkginfo)
    if owner is not None:
        owner = get_user(owner, strict=True)['id']
    action = 'add'
    if update:
        action = 'update'
    elif bool(block):
        action = 'block'
    if policy:
        context.session.assertLogin()
        policy_data = {'tag': tag_id, 'action': action, 'package': pkginfo, 'force': force}
        assert_policy('package_list', policy_data, force=force)
    if not pkg:
        pkg = lookup_package(pkginfo, create=True)
    # validate arches before running callbacks
    extra_arches = koji.parse_arches(extra_arches, strict=True, allow_none=True)
    user = get_user(context.session.user_id)
    koji.plugin.run_callbacks('prePackageListChange', action=action,
                              tag=tag, package=pkg, owner=owner,
                              block=block, extra_arches=extra_arches,
                              force=force, update=update, user=user)
    # first check to see if package is:
    #   already present (via inheritance)
    #   blocked
    pkglist = readPackageList(tag_id, pkgID=pkg['id'], inherit=True)
    previous = pkglist.get(pkg['id'], None)
    changed = False
    changed_owner = False
    if previous is None:
        block = bool(block)
        if update and not force:
            # if update flag is true, require that there be a previous entry
            raise koji.GenericError("cannot update: tag %s has no data for package %s"
                                    % (tag['name'], pkg['name']))
    else:
        # already there (possibly via inheritance)
        if owner is None:
            owner = previous['owner_id']
        changed_owner = previous['owner_id'] != owner
        if block is None:
            block = previous['blocked']
        else:
            block = bool(block)
        if extra_arches is None:
            extra_arches = previous['extra_arches']
        # see if the data is the same
        for key, value in (('blocked', block),
                           ('extra_arches', extra_arches)):
            if previous[key] != value:
                changed = True
                break
        if not changed and not changed_owner and not force:
            # no point in adding it again with the same data
            return
        if previous['blocked'] and not block and not force:
            raise koji.GenericError("package %s is blocked in tag %s" % (pkg['name'], tag['name']))
    if owner is None:
        if force:
            owner = context.session.user_id
        else:
            raise koji.GenericError("owner not specified")
    if not previous or changed:
        _pkglist_add(tag_id, pkg['id'], owner, block, extra_arches)
    elif changed_owner:
        _pkglist_owner_add(tag_id, pkg['id'], owner)
    koji.plugin.run_callbacks('postPackageListChange', action=action,
                              tag=tag, package=pkg, owner=owner,
                              block=block, extra_arches=extra_arches,
                              force=force, update=update, user=user)


def pkglist_remove(taginfo, pkginfo, force=False):
    """Remove package from the list for tag

    Most of the time you really want to use the block or unblock functions

    The main reason to remove an entry like this is to remove an override so
    that the package data can be inherited from elsewhere.
    """
    _direct_pkglist_remove(taginfo, pkginfo, force, policy=True)


def _direct_pkglist_remove(taginfo, pkginfo, force=False, policy=False):
    """Like pkglist_remove, but without policy check"""
    tag = get_tag(taginfo, strict=True)
    pkg = lookup_package(pkginfo, strict=True)
    if policy:
        context.session.assertLogin()
        policy_data = {'tag': tag['id'], 'action': 'remove', 'package': pkg['id'], 'force': force}
        # don't check policy for admins using force
        assert_policy('package_list', policy_data, force=force)

    user = get_user(context.session.user_id)
    koji.plugin.run_callbacks(
        'prePackageListChange', action='remove', tag=tag, package=pkg, user=user)
    _pkglist_remove(tag['id'], pkg['id'])
    koji.plugin.run_callbacks(
        'postPackageListChange', action='remove', tag=tag, package=pkg, user=user)


def pkglist_block(taginfo, pkginfo, force=False):
    """Block the package in tag"""
    # check pkg list existence
    tag = get_tag(taginfo, strict=True)
    pkg = lookup_package(pkginfo, strict=True)
    if not readPackageList(tag['id'], pkgID=pkg['id'], inherit=True):
        raise koji.GenericError("Package %s is not in tag listing for %s" %
                                (pkg['name'], tag['name']))
    pkglist_add(taginfo, pkginfo, block=True, force=force)


def pkglist_unblock(taginfo, pkginfo, force=False):
    """Unblock the package in tag

    Generally this just adds a unblocked duplicate of the blocked entry.
    However, if the block is actually in tag directly (not through inheritance),
    the blocking entry is simply removed"""
    tag = get_tag(taginfo, strict=True)
    pkg = lookup_package(pkginfo, strict=True)
    context.session.assertLogin()
    policy_data = {'tag': tag['id'], 'action': 'unblock', 'package': pkg['id'], 'force': force}
    # don't check policy for admins using force
    assert_policy('package_list', policy_data, force=force)
    user = get_user(context.session.user_id)
    koji.plugin.run_callbacks(
        'prePackageListChange', action='unblock', tag=tag, package=pkg, user=user)
    tag_id = tag['id']
    pkg_id = pkg['id']
    pkglist = readPackageList(tag_id, pkgID=pkg_id, inherit=True)
    previous = pkglist.get(pkg_id, None)
    if previous is None:
        raise koji.GenericError("no data (blocked or otherwise) for package %s in tag %s"
                                % (pkg['name'], tag['name']))
    if not previous['blocked']:
        raise koji.GenericError("package %s NOT blocked in tag %s" % (pkg['name'], tag['name']))
    if previous['tag_id'] != tag_id:
        _pkglist_add(tag_id, pkg_id, previous['owner_id'], False, previous['extra_arches'])
    else:
        # just remove the blocking entry
        _pkglist_remove(tag_id, pkg_id)
        # it's possible this was the only entry in the inheritance or that the next entry
        # back is also a blocked entry. if so, we need to add it back as unblocked
        pkglist = readPackageList(tag_id, pkgID=pkg_id, inherit=True)
        if pkg_id not in pkglist or pkglist[pkg_id]['blocked']:
            _pkglist_add(tag_id, pkg_id, previous['owner_id'], False, previous['extra_arches'])
    koji.plugin.run_callbacks(
        'postPackageListChange', action='unblock', tag=tag, package=pkg, user=user)


def pkglist_setowner(taginfo, pkginfo, owner, force=False):
    """Set the owner for package in tag"""
    pkglist_add(taginfo, pkginfo, owner=owner, force=force, update=True)


def pkglist_setarches(taginfo, pkginfo, arches, force=False):
    """Set extra_arches for package in tag"""
    pkglist_add(taginfo, pkginfo, extra_arches=arches, force=force, update=True)


def readPackageList(tagID=None, userID=None, pkgID=None, event=None, inherit=False,
                    with_dups=False):
    """Returns the package list for the specified tag or user.

    One of (tagID,userID,pkgID) must be specified

    Note that the returned data includes blocked entries
    """
    if tagID is None and userID is None and pkgID is None:
        raise koji.GenericError('tag,user, and/or pkg must be specified')

    packages = {}
    fields = (('package.id', 'package_id'), ('package.name', 'package_name'),
              ('tag.id', 'tag_id'), ('tag.name', 'tag_name'),
              ('users.id', 'owner_id'), ('users.name', 'owner_name'),
              ('extra_arches', 'extra_arches'),
              ('tag_packages.blocked', 'blocked'))
    flist = ', '.join([pair[0] for pair in fields])
    cond1 = eventCondition(event, table='tag_packages')
    cond2 = eventCondition(event, table='tag_package_owners')
    q = """
    SELECT %(flist)s
    FROM tag_packages
    JOIN tag on tag.id = tag_packages.tag_id
    JOIN package ON package.id = tag_packages.package_id
    JOIN tag_package_owners ON
        tag_packages.tag_id = tag_package_owners.tag_id AND
        tag_packages.package_id = tag_package_owners.package_id
    JOIN users ON users.id = tag_package_owners.owner
    WHERE %(cond1)s AND %(cond2)s"""
    if tagID is not None:
        q += """
        AND tag.id = %%(tagID)i"""
    if userID is not None:
        q += """
        AND users.id = %%(userID)i"""
    if pkgID is not None:
        if isinstance(pkgID, int):
            q += """
            AND package.id = %%(pkgID)i"""
        else:
            q += """
            AND package.name = %%(pkgID)s"""

    q = q % locals()
    for p in _multiRow(q, locals(), [pair[1] for pair in fields]):
        # things are simpler for the first tag
        pkgid = p['package_id']
        if with_dups:
            packages.setdefault(pkgid, []).append(p)
        else:
            packages[pkgid] = p

    if tagID is None or (not inherit):
        return packages

    order = readFullInheritance(tagID, event)

    re_cache = {}
    for link in order:
        tagID = link['parent_id']
        filter = link['filter']
        # precompile filter patterns
        re_list = []
        for pat in filter:
            prog = re_cache.get(pat, None)
            if prog is None:
                prog = re.compile(pat)
                re_cache[pat] = prog
            re_list.append(prog)
        # same query as before, with different params
        for p in _multiRow(q, locals(), [pair[1] for pair in fields]):
            pkgid = p['package_id']
            if not with_dups and pkgid in packages:
                # previous data supercedes
                continue
            # apply package filters
            skip = False
            for prog in re_list:
                # the list of filters is cumulative, i.e.
                # the package name must match all of them
                if prog.match(p['package_name']) is None:
                    skip = True
                    break
            if skip:
                continue
            if with_dups:
                packages.setdefault(pkgid, []).append(p)
            else:
                packages[pkgid] = p
    return packages


def list_tags(build=None, package=None, perms=True, queryOpts=None, pattern=None):
    """List tags according to filters

    :param int|str build: If build is specified, only return tags associated with
                          the given build.  Build can be either an integer ID or
                          a string N-V-R.
    :param int|str package: If package is specified, only return tags associated with the
                            specified package. Package can be either an integer ID or a
                            string name.

                            In this case resulting map will have additional keys:
                              - owner_id
                              - owner_name
                              - blocked
                              - extra_arches
    :param bool perms: If perms is True, perm_id and perm is added to resulting maps.
    :param dict queryOpts: hash with query options for QueryProcessor
    :param pattern: If glob pattern is specified, only return tags matching that pattern.

    :returns list of dicts: Each map contains id, name, arches and locked keys and
                            additional keys as specified via package or perms options.
    """
    if build is not None and package is not None:
        raise koji.GenericError('only one of build and package may be specified')

    tables = ['tag_config']
    joins = ['tag ON tag.id = tag_config.tag_id']
    fields = ['tag.id', 'tag.name', 'tag_config.arches', 'tag_config.locked',
              'tag_config.maven_support', 'tag_config.maven_include_all']
    aliases = ['id', 'name', 'arches', 'locked', 'maven_support', 'maven_include_all']
    clauses = ['tag_config.active = true']
    if perms:
        joins.append('LEFT OUTER JOIN permissions ON tag_config.perm_id = permissions.id')
        fields.extend(['tag_config.perm_id', 'permissions.name'])
        aliases.extend(['perm_id', 'perm'])

    if build is not None:
        # lookup build id
        buildinfo = get_build(build)
        if not buildinfo:
            raise koji.GenericError('invalid build: %s' % build)
        joins.append('tag_listing ON tag.id = tag_listing.tag_id')
        clauses.append('tag_listing.active = true')
        clauses.append('tag_listing.build_id = %(buildID)i')
        buildID = buildinfo['id']
    elif package is not None:
        packageinfo = lookup_package(package)
        if not packageinfo:
            raise koji.GenericError('invalid package: %s' % package)
        fields.extend(
            ['users.id', 'users.name', 'tag_packages.blocked', 'tag_packages.extra_arches'])
        aliases.extend(['owner_id', 'owner_name', 'blocked', 'extra_arches'])
        joins.append('tag_packages ON tag.id = tag_packages.tag_id')
        clauses.append('tag_packages.active = true')
        clauses.append('tag_packages.package_id = %(packageID)i')
        joins.append("tag_package_owners ON\n"
                     "   tag_packages.tag_id = tag_package_owners.tag_id AND\n"
                     "   tag_packages.package_id = tag_package_owners.package_id AND\n"
                     "   tag_package_owners.active IS TRUE")
        joins.append('users ON tag_package_owners.owner = users.id')
        packageID = packageinfo['id']
    if pattern is not None:
        # copied from _prepareSearchTerms / glob
        pattern = pattern.replace(
            '\\', '\\\\').replace('_', r'\_').replace('?', '_').replace('*', '%')
        clauses.append('tag.name ILIKE %(pattern)s')

    query = QueryProcessor(columns=fields, aliases=aliases, tables=tables,
                           joins=joins, clauses=clauses, values=locals(),
                           opts=queryOpts)
    return query.iterate()


def readTaggedBuilds(tag, event=None, inherit=False, latest=False, package=None, owner=None,
                     type=None):
    """Returns a list of builds for specified tag

    set inherit=True to follow inheritance
    set event to query at a time in the past
    set latest=True to get only the latest build per package
    set latest=N to get only the N latest tagged RPMs

    If type is not None, restrict the list to builds of the given type.  Currently the supported
    types are 'maven', 'win', and 'image'.
    """
    # build - id pkg_id version release epoch
    # tag_listing - id build_id tag_id

    if not isinstance(latest, NUMERIC_TYPES):
        latest = bool(latest)

    taglist = [tag]
    if inherit:
        taglist += [link['parent_id'] for link in readFullInheritance(tag, event)]

    # regardless of inherit setting, we need to use inheritance to read the
    # package list
    packages = readPackageList(tagID=tag, event=event, inherit=True, pkgID=package)

    # these values are used for each iteration
    fields = [('tag.id', 'tag_id'), ('tag.name', 'tag_name'), ('build.id', 'id'),
              ('build.id', 'build_id'), ('build.version', 'version'), ('build.release', 'release'),
              ('build.epoch', 'epoch'), ('build.state', 'state'),
              ('build.completion_time', 'completion_time'),
              ('build.start_time', 'start_time'),
              ('build.task_id', 'task_id'),
              ('events.id', 'creation_event_id'), ('events.time', 'creation_time'),
              ('volume.id', 'volume_id'), ('volume.name', 'volume_name'),
              ('package.id', 'package_id'), ('package.name', 'package_name'),
              ('package.name', 'name'),
              ("package.name || '-' || build.version || '-' || build.release", 'nvr'),
              ('users.id', 'owner_id'), ('users.name', 'owner_name')]
    st_complete = koji.BUILD_STATES['COMPLETE']

    type_join = ''
    if type is None:
        pass
    elif type == 'maven':
        type_join = 'JOIN maven_builds ON maven_builds.build_id = tag_listing.build_id'
        fields.extend([('maven_builds.group_id', 'maven_group_id'),
                       ('maven_builds.artifact_id', 'maven_artifact_id'),
                       ('maven_builds.version', 'maven_version')])
    elif type == 'win':
        type_join = 'JOIN win_builds ON win_builds.build_id = tag_listing.build_id'
        fields.append(('win_builds.platform', 'platform'))
    elif type == 'image':
        type_join = 'JOIN image_builds ON image_builds.build_id = tag_listing.build_id'
        fields.append(('image_builds.build_id', 'build_id'))
    else:
        btype = lookup_name('btype', type, strict=False)
        if not btype:
            raise koji.GenericError('unsupported build type: %s' % type)
        btype_id = btype['id']
        type_join = ('JOIN build_types ON build.id = build_types.build_id '
                     'AND btype_id = %(btype_id)s')

    q = """SELECT %s
    FROM tag_listing
    JOIN tag ON tag.id = tag_listing.tag_id
    JOIN build ON build.id = tag_listing.build_id
    %s
    JOIN users ON users.id = build.owner
    JOIN events ON events.id = build.create_event
    JOIN package ON package.id = build.pkg_id
    JOIN volume ON volume.id = build.volume_id
    WHERE %s AND tag_id=%%(tagid)s
        AND build.state=%%(st_complete)i
    """ % (', '.join([pair[0] for pair in fields]), type_join,
           eventCondition(event, 'tag_listing'))
    if package:
        q += """AND package.name = %(package)s
        """
    if owner:
        q += """AND users.name = %(owner)s
        """
    q += """ORDER BY tag_listing.create_event DESC
    """
    # i.e. latest first

    builds = []
    seen = {}   # used to enforce the 'latest' option
    for tagid in taglist:
        # log_error(koji.db._quoteparams(q,locals()))
        for build in _multiRow(q, locals(), [pair[1] for pair in fields]):
            pkgid = build['package_id']
            pinfo = packages.get(pkgid, None)
            if pinfo is None or pinfo['blocked']:
                # note:
                # tools should endeavor to keep tag_listing sane w.r.t.
                # the package list, but if there is disagreement the package
                # list should take priority
                continue
            if latest:
                if (latest is True and pkgid in seen) or seen.get(pkgid, 0) >= latest:
                    # only take the first N entries
                    # (note ordering in query above)
                    continue
                seen[pkgid] = seen.get(pkgid, 0) + 1
            builds.append(build)

    return builds


def readTaggedRPMS(tag, package=None, arch=None, event=None, inherit=False, latest=True,
                   rpmsigs=False, owner=None, type=None):
    """Returns a list of rpms for specified tag

    set inherit=True to follow inheritance
    set event to query at a time in the past
    set latest=False to get all tagged RPMS (not just from the latest builds)
    set latest=N to get only the N latest tagged RPMs

    If type is not None, restrict the list to rpms from builds of the given type.  Currently the
    supported types are 'maven' and 'win'.
    """
    taglist = [tag]
    if inherit:
        # XXX really should cache this - it gets called several places
        #   (however, it is fairly quick)
        taglist += [link['parent_id'] for link in readFullInheritance(tag, event)]

    builds = readTaggedBuilds(tag, event=event, inherit=inherit, latest=latest, package=package,
                              owner=owner, type=type)
    # index builds
    build_idx = dict([(b['build_id'], b) for b in builds])

    # the following query is run for each tag in the inheritance
    fields = [('rpminfo.name', 'name'),
              ('rpminfo.version', 'version'),
              ('rpminfo.release', 'release'),
              ('rpminfo.arch', 'arch'),
              ('rpminfo.id', 'id'),
              ('rpminfo.epoch', 'epoch'),
              ('rpminfo.payloadhash', 'payloadhash'),
              ('rpminfo.size', 'size'),
              ('rpminfo.buildtime', 'buildtime'),
              ('rpminfo.buildroot_id', 'buildroot_id'),
              ('rpminfo.build_id', 'build_id'),
              ('rpminfo.metadata_only', 'metadata_only'),
              ('rpminfo.extra', 'extra'),
              ]
    tables = ['rpminfo']
    joins = ['tag_listing ON rpminfo.build_id = tag_listing.build_id']
    clauses = [eventCondition(event, 'tag_listing'), 'tag_id=%(tagid)s']
    data = {}  # tagid added later
    if package:
        joins.append('build ON rpminfo.build_id = build.id')
        joins.append('package ON package.id = build.pkg_id')
        clauses.append('package.name = %(package)s')
        data['package'] = package
    if rpmsigs:
        fields.append(('rpmsigs.sigkey', 'sigkey'))
        joins.append('LEFT OUTER JOIN rpmsigs on rpminfo.id = rpmsigs.rpm_id')
    if arch:
        data['arch'] = arch
        if isinstance(arch, str):
            clauses.append('rpminfo.arch = %(arch)s')
        elif isinstance(arch, (list, tuple)):
            clauses.append('rpminfo.arch IN %(arch)s')
        else:
            raise koji.GenericError('invalid arch option: %s' % arch)

    fields, aliases = zip(*fields)
    query = QueryProcessor(tables=tables, joins=joins, clauses=clauses,
                           columns=fields, aliases=aliases, values=data, transform=_fix_rpm_row)

    # unique constraints ensure that each of these queries will not report
    # duplicate rpminfo entries, BUT since we make the query multiple times,
    # we can get duplicates if a package is multiply tagged.
    tags_seen = {}

    def _iter_rpms():
        for tagid in taglist:
            if tagid in tags_seen:
                # certain inheritance trees can (legitimately) have the same tag
                # appear more than once (perhaps once with a package filter and once
                # without). The hard part of that was already done by readTaggedBuilds.
                # We only need consider each tag once. Note how we use build_idx below.
                # (Without this, we could report the same rpm twice)
                continue
            else:
                tags_seen[tagid] = 1
            query.values['tagid'] = tagid
            for rpminfo in query.iterate():
                # note: we're checking against the build list because
                # it has been filtered by the package list. The tag
                # tools should endeavor to keep tag_listing sane w.r.t.
                # the package list, but if there is disagreement the package
                # list should take priority
                build = build_idx.get(rpminfo['build_id'], None)
                if build is None:
                    continue
                elif build['tag_id'] != tagid:
                    # wrong tag
                    continue
                yield rpminfo
    return [_iter_rpms(), builds]


def readTaggedArchives(tag, package=None, event=None, inherit=False, latest=True, type=None):
    """Returns a list of archives for specified tag

    set inherit=True to follow inheritance
    set event to query at a time in the past
    set latest=False to get all tagged archives (not just from the latest builds)
    set latest=N to get only the N latest tagged RPMs

    If type is not None, restrict the listing to archives of the given type.  Currently
    the supported types are 'maven' and 'win'.
    """
    taglist = [tag]
    if inherit:
        # XXX really should cache this - it gets called several places
        #   (however, it is fairly quick)
        taglist += [link['parent_id'] for link in readFullInheritance(tag, event)]

    # If type == 'maven', we require that both the build *and* the archive have Maven metadata
    builds = readTaggedBuilds(tag, event=event, inherit=inherit, latest=latest, package=package,
                              type=type)
    # index builds
    build_idx = dict([(b['build_id'], b) for b in builds])

    # the following query is run for each tag in the inheritance
    fields = [('archiveinfo.id', 'id'),
              ('archiveinfo.type_id', 'type_id'),
              ('archiveinfo.btype_id', 'btype_id'),
              ('btype.name', 'btype'),
              ('archiveinfo.build_id', 'build_id'),
              ('archiveinfo.buildroot_id', 'buildroot_id'),
              ('archiveinfo.filename', 'filename'),
              ('archiveinfo.size', 'size'),
              ('archiveinfo.checksum', 'checksum'),
              ('archiveinfo.checksum_type', 'checksum_type'),
              ('archiveinfo.metadata_only', 'metadata_only'),
              ('archiveinfo.extra', 'extra'),
              ]
    tables = ['archiveinfo']
    joins = ['tag_listing ON archiveinfo.build_id = tag_listing.build_id',
             'btype ON archiveinfo.btype_id = btype.id']
    clauses = [eventCondition(event), 'tag_listing.tag_id = %(tagid)i']
    if package:
        joins.append('build ON archiveinfo.build_id = build.id')
        joins.append('package ON build.pkg_id = package.id')
        clauses.append('package.name = %(package)s')
    if type is None:
        pass
    elif type == 'maven':
        joins.append('maven_archives ON archiveinfo.id = maven_archives.archive_id')
        fields.extend([('maven_archives.group_id', 'maven_group_id'),
                       ('maven_archives.artifact_id', 'maven_artifact_id'),
                       ('maven_archives.version', 'maven_version')])
    elif type == 'win':
        joins.append('win_archives ON archiveinfo.id = win_archives.archive_id')
        fields.extend([('win_archives.relpath', 'relpath'),
                       ('win_archives.platforms', 'platforms'),
                       ('win_archives.flags', 'flags')])
    else:
        raise koji.GenericError('unsupported archive type: %s' % type)

    query = QueryProcessor(tables=tables, joins=joins, clauses=clauses,
                           transform=_fix_archive_row,
                           columns=[pair[0] for pair in fields],
                           aliases=[pair[1] for pair in fields])

    # unique constraints ensure that each of these queries will not report
    # duplicate archiveinfo entries, BUT since we make the query multiple times,
    # we can get duplicates if a package is multiply tagged.
    archives = []
    tags_seen = {}
    for tagid in taglist:
        if tagid in tags_seen:
            # certain inheritance trees can (legitimately) have the same tag
            # appear more than once (perhaps once with a package filter and once
            # without). The hard part of that was already done by readTaggedBuilds.
            # We only need consider each tag once. Note how we use build_idx below.
            # (Without this, we could report the same rpm twice)
            continue
        else:
            tags_seen[tagid] = 1
        query.values = {'tagid': tagid, 'package': package}
        for archiveinfo in query.execute():
            # note: we're checking against the build list because
            # it has been filtered by the package list. The tag
            # tools should endeavor to keep tag_listing sane w.r.t.
            # the package list, but if there is disagreement the package
            # list should take priority
            build = build_idx.get(archiveinfo['build_id'], None)
            if build is None:
                continue
            elif build['tag_id'] != tagid:
                # wrong tag
                continue
            archives.append(archiveinfo)
    return [archives, builds]


def check_tag_access(tag_id, user_id=None):
    """Determine if user has access to tag package with tag.

    Returns a tuple (access, override, reason)
        access: a boolean indicating whether access is allowed
        override: a boolean indicating whether access may be forced
        reason: the reason access is blocked
    """
    if user_id is None:
        user_id = context.session.user_id
    if user_id is None:
        raise koji.GenericError("a user_id is required")
    perms = koji.auth.get_user_perms(user_id)
    override = False
    if 'admin' in perms:
        override = True
    tag = get_tag(tag_id, strict=True)
    if tag['locked']:
        return (False, override, "tag is locked")
    if tag['perm_id']:
        needed_perm = lookup_perm(tag['perm_id'], strict=True)['name']
        if needed_perm not in perms:
            return (False, override, "tag requires %s permission" % needed_perm)
    return (True, override, "")


def assert_tag_access(tag_id, user_id=None, force=False):
    access, override, reason = check_tag_access(tag_id, user_id)
    if not access and not (override and force):
        raise koji.ActionNotAllowed(reason)


def _tag_build(tag, build, user_id=None, force=False):
    """Tag a build

    This function makes access checks based on user_id, which defaults to the
    user_id of the session.

    Tagging with a locked tag is not allowed unless force is true (and even
    then admin permission is required).

    Retagging is not allowed unless force is true. (retagging changes the order
    of entries will affect which build is the latest)
    """
    tag = get_tag(tag, strict=True)
    build = get_build(build, strict=True)
    if user_id:
        user = get_user(user_id, strict=True)
    else:
        # use the user associated with the current session
        user = get_user(context.session.user_id, strict=True)
    # access check
    assert_tag_access(tag['id'], user_id=user_id, force=force)
    return _direct_tag_build(tag, build, user, force)


def _direct_tag_build(tag, build, user, force=False):
    """Directly tag a build. No access check or value lookup."""
    koji.plugin.run_callbacks('preTag', tag=tag, build=build, user=user, force=force)
    tag_id = tag['id']
    build_id = build['id']
    user_id = user['id']
    nvr = "%(name)s-%(version)s-%(release)s" % build
    if build['state'] != koji.BUILD_STATES['COMPLETE']:
        # incomplete builds may not be tagged, not even when forced
        state = koji.BUILD_STATES[build['state']]
        raise koji.TagError("build %s not complete: state %s" % (nvr, state))
    # see if it's already tagged
    retag = False
    table = 'tag_listing'
    clauses = ('tag_id=%(tag_id)i', 'build_id=%(build_id)i')
    query = QueryProcessor(columns=['build_id'], tables=[table],
                           clauses=('active = TRUE',) + clauses,
                           values=locals(), opts={'rowlock': True})
    # note: tag_listing is unique on (build_id, tag_id, active)
    if query.executeOne():
        # already tagged
        if not force:
            raise koji.TagError("build %s already tagged (%s)" % (nvr, tag['name']))
        # otherwise we retag
        retag = True
    if retag:
        # revoke the old tag first
        update = UpdateProcessor(table, values=locals(), clauses=clauses)
        update.make_revoke(user_id=user_id)
        update.execute()
    # tag the package
    insert = InsertProcessor(table)
    insert.set(tag_id=tag_id, build_id=build_id)
    insert.make_create(user_id=user_id)
    insert.execute()
    koji.plugin.run_callbacks('postTag', tag=tag, build=build, user=user, force=force)


def _untag_build(tag, build, user_id=None, strict=True, force=False):
    """Untag a build

    If strict is true, assert that build is actually tagged
    The force option overrides a lock (if the user is an admin)

    This function makes access checks based on user_id, which defaults to the
    user_id of the session.
    """
    tag = get_tag(tag, strict=True)
    build = get_build(build, strict=True)
    if user_id:
        user = get_user(user_id, strict=True)
    else:
        # use the user associated with the current session
        user = get_user(context.session.user_id, strict=True)
    assert_tag_access(tag['id'], user_id=user_id, force=force)
    return _direct_untag_build(tag, build, user, strict, force)


def _direct_untag_build(tag, build, user, strict=True, force=False):
    """Directly untag a build. No access check or value lookup."""
    koji.plugin.run_callbacks(
        'preUntag', tag=tag, build=build, user=user, force=force, strict=strict)
    values = {'tag_id': tag['id'], 'build_id': build['id']}
    update = UpdateProcessor('tag_listing', values=values,
                             clauses=['tag_id=%(tag_id)i', 'build_id=%(build_id)i'])
    update.make_revoke(user_id=user['id'])
    count = update.execute()
    if count == 0 and strict:
        nvr = "%(name)s-%(version)s-%(release)s" % build
        raise koji.TagError("build %s not in tag %s" % (nvr, tag['name']))
    koji.plugin.run_callbacks(
        'postUntag', tag=tag, build=build, user=user, force=force, strict=strict)


# tag-group operations
#       add
#       remove
#       block
#       unblock
#       list (readTagGroups)


def grplist_add(taginfo, grpinfo, block=False, force=False, **opts):
    """Add to (or update) group list for tag"""
    # only admins....
    context.session.assertPerm('tag')
    _grplist_add(taginfo, grpinfo, block, force, **opts)


def _grplist_add(taginfo, grpinfo, block, force, **opts):
    """grplist_add without permission check"""
    tag = get_tag(taginfo, strict=True)
    group = lookup_group(grpinfo, create=True)
    opts['blocked'] = bool(block)
    # check current group status (incl inheritance)
    groups = get_tag_groups(tag['id'], inherit=True, incl_pkgs=False, incl_reqs=False)
    previous = groups.get(group['id'], None)
    cfg_fields = ('exported', 'display_name', 'is_default', 'uservisible',
                  'description', 'langonly', 'biarchonly', 'blocked')
    # prevent user-provided opts from doing anything strange
    opts = dslice(opts, cfg_fields, strict=False)
    if previous is not None:
        # already there (possibly via inheritance)
        if previous['blocked'] and not force:
            raise koji.GenericError("group %s is blocked in tag %s" % (group['name'], tag['name']))
        # check for duplication and grab old data for defaults
        changed = False
        for field in cfg_fields:
            old = previous[field]
            if field in opts:
                if opts[field] != old:
                    changed = True
            else:
                opts[field] = old
        if not changed:
            # no point in adding it again with the same data
            return
    # provide available defaults and sanity check data
    opts.setdefault('display_name', group['name'])
    opts.setdefault('biarchonly', False)
    opts.setdefault('exported', True)
    opts.setdefault('uservisible', True)
    # XXX ^^^
    opts['tag_id'] = tag['id']
    opts['group_id'] = group['id']
    # revoke old entry (if present)
    update = UpdateProcessor('group_config', values=opts,
                             clauses=['group_id=%(group_id)s', 'tag_id=%(tag_id)s'])
    update.make_revoke()
    update.execute()
    # add new entry
    insert = InsertProcessor('group_config', data=opts)
    insert.make_create()
    insert.execute()


def grplist_remove(taginfo, grpinfo, force=False):
    """Remove group from the list for tag
    Permission required: admin

    :param taginfo: tag id or name which group is removed from
    :type taginfo: int or str
    :param grpinfo: group id or name which is removed
    :type grpinfo: int or str
    :param bool force: If False(default), GenericException will be raised when
                       no group found in the list for tag. If True, revoking
                       will be force to execute, no matter if the relationship
                       exists.

    Really this shouldn't be used except in special cases
    Most of the time you really want to use the block or unblock functions
    """
    # only admins....
    context.session.assertPerm('tag')
    _grplist_remove(taginfo, grpinfo, force)


def _grplist_remove(taginfo, grpinfo, force=False):
    """grplist_remove without permission check"""
    tag = get_tag(taginfo, strict=True)
    group = lookup_group(grpinfo, strict=True)
    tag_id = tag['id']
    grp_id = group['id']
    clauses = ['group_id=%(grp_id)s', 'tag_id=%(tag_id)s']
    if not force:
        query = QueryProcessor(columns=['group_id', 'tag_id', 'active'],
                               tables=['group_config'],
                               values=locals(),
                               clauses=clauses + [eventCondition(None)])
        old_grp_conf = query.executeOne()
        if not old_grp_conf:
            raise koji.GenericError("No group: %s found for tag: %s"
                                    % (group['name'], tag['name']))
    update = UpdateProcessor('group_config', values=locals(), clauses=clauses)
    update.make_revoke()
    update.execute()


def grplist_block(taginfo, grpinfo):
    """Block the group in tag"""
    grplist_add(taginfo, grpinfo, block=True)


def grplist_unblock(taginfo, grpinfo):
    """Unblock the group in tag

    If the group is blocked in this tag, then simply remove the block.
    Otherwise, raise an error
    """
    # only admins...
    context.session.assertPerm('tag')
    _grplist_unblock(taginfo, grpinfo)


def _grplist_unblock(taginfo, grpinfo):
    """grplist_unblock without permssion check"""
    tag = lookup_tag(taginfo, strict=True)
    group = lookup_group(grpinfo, strict=True)
    tag_id = tag['id']
    grp_id = group['id']
    table = 'group_config'
    clauses = ('group_id=%(grp_id)s', 'tag_id=%(tag_id)s')
    query = QueryProcessor(columns=['blocked'], tables=[table],
                           clauses=('active = TRUE',) + clauses,
                           values=locals(), opts={'rowlock': True})
    blocked = query.singleValue(strict=False)
    if not blocked:
        raise koji.GenericError("group %s is NOT blocked in tag %s" % (group['name'], tag['name']))
    update = UpdateProcessor(table, values=locals(), clauses=clauses)
    update.make_revoke()
    update.execute()


# tag-group-pkg operations
#       add
#       remove
#       block
#       unblock
#       list (readTagGroups)


def grp_pkg_add(taginfo, grpinfo, pkg_name, block=False, force=False, **opts):
    """Add package to group for tag"""
    # only admins....
    context.session.assertPerm('tag')
    _grp_pkg_add(taginfo, grpinfo, pkg_name, block, force, **opts)


def _grp_pkg_add(taginfo, grpinfo, pkg_name, block, force, **opts):
    """grp_pkg_add without permssion checks"""
    tag = lookup_tag(taginfo, strict=True)
    group = lookup_group(grpinfo, strict=True)
    block = bool(block)
    # check current group status (incl inheritance)
    groups = get_tag_groups(tag['id'], inherit=True, incl_pkgs=True, incl_reqs=False)
    grp_cfg = groups.get(group['id'], None)
    if grp_cfg is None:
        raise koji.GenericError("group %s not present in tag %s" % (group['name'], tag['name']))
    elif grp_cfg['blocked']:
        raise koji.GenericError("group %s is blocked in tag %s" % (group['name'], tag['name']))
    previous = grp_cfg['packagelist'].get(pkg_name, None)
    cfg_fields = ('type', 'basearchonly', 'requires')
    # prevent user-provided opts from doing anything strange
    opts = dslice(opts, cfg_fields, strict=False)
    if previous is not None:
        # already there (possibly via inheritance)
        if previous['blocked'] and not force:
            raise koji.GenericError("package %s blocked in group %s, tag %s"
                                    % (pkg_name, group['name'], tag['name']))
        # check for duplication and grab old data for defaults
        changed = False
        for field in cfg_fields:
            old = previous[field]
            if field in opts:
                if opts[field] != old:
                    changed = True
            else:
                opts[field] = old
        if block:
            # from condition above, either previous is not blocked or force is on,
            # either way, we should add the entry
            changed = True
        if not changed and not force:
            # no point in adding it again with the same data (unless force is on)
            return
    opts.setdefault('type', 'mandatory')
    opts['group_id'] = group['id']
    opts['tag_id'] = tag['id']
    opts['package'] = pkg_name
    opts['blocked'] = block
    # revoke old entry (if present)
    update = UpdateProcessor('group_package_listing', values=opts,
                             clauses=['group_id=%(group_id)s',
                                      'tag_id=%(tag_id)s',
                                      'package=%(package)s'])
    update.make_revoke()
    update.execute()
    # add new entry
    insert = InsertProcessor('group_package_listing', data=opts)
    insert.make_create()
    insert.execute()


def grp_pkg_remove(taginfo, grpinfo, pkg_name, force=False):
    """Remove package from the list for group-tag

    Really this shouldn't be used except in special cases
    Most of the time you really want to use the block or unblock functions
    """
    # only admins....
    context.session.assertPerm('tag')
    _grp_pkg_remove(taginfo, grpinfo, pkg_name, force)


def _grp_pkg_remove(taginfo, grpinfo, pkg_name, force):
    """grp_pkg_remove without permssion checks"""
    tag_id = get_tag_id(taginfo, strict=True)
    grp_id = get_group_id(grpinfo, strict=True)
    update = UpdateProcessor('group_package_listing', values=locals(),
                             clauses=['package=%(pkg_name)s',
                                      'tag_id=%(tag_id)s',
                                      'group_id = %(grp_id)s'])
    update.make_revoke()
    update.execute()


def grp_pkg_block(taginfo, grpinfo, pkg_name):
    """Block the package in group-tag"""
    grp_pkg_add(taginfo, grpinfo, pkg_name, block=True)


def grp_pkg_unblock(taginfo, grpinfo, pkg_name):
    """Unblock the package in group-tag

    If blocked (directly) in this tag, then simply remove the block.
    Otherwise, raise an error
    """
    # only admins...
    context.session.assertPerm('tag')
    _grp_pkg_unblock(taginfo, grpinfo, pkg_name)


def _grp_pkg_unblock(taginfo, grpinfo, pkg_name):
    """grp_pkg_unblock without permission checks"""
    table = 'group_package_listing'
    tag_id = get_tag_id(taginfo, strict=True)
    grp_id = get_group_id(grpinfo, strict=True)
    clauses = ('group_id=%(grp_id)s', 'tag_id=%(tag_id)s', 'package = %(pkg_name)s')
    query = QueryProcessor(columns=['blocked'], tables=[table],
                           clauses=('active = TRUE',) + clauses,
                           values=locals(), opts={'rowlock': True})
    blocked = query.singleValue(strict=False)
    if not blocked:
        raise koji.GenericError("package %s is NOT blocked in group %s, tag %s"
                                % (pkg_name, grp_id, tag_id))
    update = UpdateProcessor('group_package_listing', values=locals(), clauses=clauses)
    update.make_revoke()
    update.execute()


# tag-group-req operations
#       add
#       remove
#       block
#       unblock
#       list (readTagGroups)


def grp_req_add(taginfo, grpinfo, reqinfo, block=False, force=False, **opts):
    """Add group requirement to group for tag"""
    # only admins....
    context.session.assertPerm('tag')
    _grp_req_add(taginfo, grpinfo, reqinfo, block, force, **opts)


def _grp_req_add(taginfo, grpinfo, reqinfo, block, force, **opts):
    """grp_req_add without permssion checks"""
    tag = lookup_tag(taginfo, strict=True)
    group = lookup_group(grpinfo, strict=True, create=False)
    req = lookup_group(reqinfo, strict=True, create=False)
    block = bool(block)
    # check current group status (incl inheritance)
    groups = get_tag_groups(tag['id'], inherit=True, incl_pkgs=False, incl_reqs=True)
    grp_cfg = groups.get(group['id'], None)
    if grp_cfg is None:
        raise koji.GenericError("group %s not present in tag %s" % (group['name'], tag['name']))
    elif grp_cfg['blocked']:
        raise koji.GenericError("group %s is blocked in tag %s" % (group['name'], tag['name']))
    previous = grp_cfg['grouplist'].get(req['id'], None)
    cfg_fields = ('type', 'is_metapkg')
    # prevent user-provided opts from doing anything strange
    opts = dslice(opts, cfg_fields, strict=False)
    if previous is not None:
        # already there (possibly via inheritance)
        if previous['blocked'] and not force:
            raise koji.GenericError("requirement on group %s blocked in group %s, tag %s"
                                    % (req['name'], group['name'], tag['name']))
        # check for duplication and grab old data for defaults
        changed = False
        for field in cfg_fields:
            old = previous[field]
            if field in opts:
                if opts[field] != old:
                    changed = True
            else:
                opts[field] = old
        if block:
            # from condition above, either previous is not blocked or force is on,
            # either way, we should add the entry
            changed = True
        if not changed:
            # no point in adding it again with the same data
            return
    opts.setdefault('type', 'mandatory')
    opts['group_id'] = group['id']
    opts['tag_id'] = tag['id']
    opts['req_id'] = req['id']
    opts['blocked'] = block
    # revoke old entry (if present)
    update = UpdateProcessor('group_req_listing', values=opts,
                             clauses=['group_id=%(group_id)s',
                                      'tag_id=%(tag_id)s',
                                      'req_id=%(req_id)s'])
    update.make_revoke()
    update.execute()
    # add new entry
    insert = InsertProcessor('group_req_listing', data=opts)
    insert.make_create()
    insert.execute()


def grp_req_remove(taginfo, grpinfo, reqinfo, force=False):
    """Remove group requirement from the list for group-tag

    Really this shouldn't be used except in special cases
    Most of the time you really want to use the block or unblock functions
    """
    # only admins....
    context.session.assertPerm('tag')
    _grp_req_remove(taginfo, grpinfo, reqinfo, force)


def _grp_req_remove(taginfo, grpinfo, reqinfo, force):
    """grp_req_remove without permission checks"""
    tag_id = get_tag_id(taginfo, strict=True)
    grp_id = get_group_id(grpinfo, strict=True)
    req_id = get_group_id(reqinfo, strict=True)
    update = UpdateProcessor('group_req_listing', values=locals(),
                             clauses=['req_id=%(req_id)s',
                                      'tag_id=%(tag_id)s',
                                      'group_id = %(grp_id)s'])
    update.make_revoke()
    update.execute()


def grp_req_block(taginfo, grpinfo, reqinfo):
    """Block the group requirement in group-tag"""
    grp_req_add(taginfo, grpinfo, reqinfo, block=True)


def grp_req_unblock(taginfo, grpinfo, reqinfo):
    """Unblock the group requirement in group-tag

    If blocked (directly) in this tag, then simply remove the block.
    Otherwise, raise an error
    """
    # only admins...
    context.session.assertPerm('tag')
    _grp_req_unblock(taginfo, grpinfo, reqinfo)


def _grp_req_unblock(taginfo, grpinfo, reqinfo):
    """grp_req_unblock without permssion checks"""
    tag_id = get_tag_id(taginfo, strict=True)
    grp_id = get_group_id(grpinfo, strict=True)
    req_id = get_group_id(reqinfo, strict=True)
    table = 'group_req_listing'

    clauses = ('group_id=%(grp_id)s', 'tag_id=%(tag_id)s', 'req_id = %(req_id)s')
    query = QueryProcessor(columns=['blocked'], tables=[table],
                           clauses=('active = TRUE',) + clauses,
                           values=locals(), opts={'rowlock': True})
    blocked = query.singleValue(strict=False)
    if not blocked:
        raise koji.GenericError("group req %s is NOT blocked in group %s, tag %s"
                                % (req_id, grp_id, tag_id))
    update = UpdateProcessor('group_req_listing', values=locals(), clauses=clauses)
    update.make_revoke()
    update.execute()


def get_tag_groups(tag, event=None, inherit=True, incl_pkgs=True, incl_reqs=True):
    """Return group data for the tag

    If inherit is true, follow inheritance
    If event is specified, query at event
    If incl_pkgs is true (the default), include packagelist data
    If incl_reqs is true (the default), include groupreq data

    Note: the data returned includes some blocked entries that may need to be
    filtered out.
    """
    order = None
    tag = get_tag_id(tag, strict=True)
    taglist = [tag]
    if inherit:
        order = readFullInheritance(tag, event)
        taglist += [link['parent_id'] for link in order]
    evcondition = eventCondition(event)

    # First get the list of groups
    fields = ('name', 'group_id', 'tag_id', 'blocked', 'exported', 'display_name',
              'is_default', 'uservisible', 'description', 'langonly', 'biarchonly',)
    q = """
    SELECT %s FROM group_config JOIN groups ON group_id = id
    WHERE %s AND tag_id = %%(tagid)s
    """ % (",".join(fields), evcondition)
    groups = {}
    for tagid in taglist:
        for group in _multiRow(q, locals(), fields):
            grp_id = group['group_id']
            # we only take the first entry for group as we go through inheritance
            groups.setdefault(grp_id, group)

    if incl_pkgs:
        for group in groups.values():
            group['packagelist'] = {}
        fields = ('group_id', 'tag_id', 'package', 'blocked', 'type', 'basearchonly', 'requires')
        q = """
        SELECT %s FROM group_package_listing
        WHERE %s AND tag_id = %%(tagid)s
        """ % (",".join(fields), evcondition)
        for tagid in taglist:
            for grp_pkg in _multiRow(q, locals(), fields):
                grp_id = grp_pkg['group_id']
                if grp_id not in groups:
                    # tag does not have this group
                    continue
                group = groups[grp_id]
                if group['blocked']:
                    # ignore blocked groups
                    continue
                pkg_name = grp_pkg['package']
                group['packagelist'].setdefault(pkg_name, grp_pkg)

    if incl_reqs:
        # and now the group reqs
        for group in groups.values():
            group['grouplist'] = {}
        fields = ('group_id', 'tag_id', 'req_id', 'blocked', 'type', 'is_metapkg', 'name')
        q = """SELECT %s FROM group_req_listing JOIN groups on req_id = id
        WHERE %s AND tag_id = %%(tagid)s
        """ % (",".join(fields), evcondition)
        for tagid in taglist:
            for grp_req in _multiRow(q, locals(), fields):
                grp_id = grp_req['group_id']
                if grp_id not in groups:
                    # tag does not have this group
                    continue
                group = groups[grp_id]
                if group['blocked']:
                    # ignore blocked groups
                    continue
                req_id = grp_req['req_id']
                if req_id not in groups:
                    # tag does not have this group
                    continue
                elif groups[req_id]['blocked']:
                    # ignore blocked groups
                    continue
                group['grouplist'].setdefault(req_id, grp_req)

    return groups


def readTagGroups(tag, event=None, inherit=True, incl_pkgs=True, incl_reqs=True,
                  incl_blocked=False):
    """Return group data for the tag with blocked entries removed

    Also scrubs data into an xmlrpc-safe format (no integer keys)

    Blocked packages/groups can alternatively also be listed if incl_blocked is set to True
    """
    groups = get_tag_groups(tag, event, inherit, incl_pkgs, incl_reqs)
    groups = to_list(groups.values())
    for group in groups:
        # filter blocked entries and collapse to a list
        if 'packagelist' in group:
            if incl_blocked:
                group['packagelist'] = to_list(group['packagelist'].values())
            else:
                group['packagelist'] = [x for x in group['packagelist'].values()
                                        if not x['blocked']]
        if 'grouplist' in group:
            if incl_blocked:
                group['grouplist'] = to_list(group['grouplist'].values())
            else:
                group['grouplist'] = [x for x in group['grouplist'].values()
                                      if not x['blocked']]
    # filter blocked entries and collapse to a list
    if incl_blocked:
        return groups
    else:
        return [x for x in groups if not x['blocked']]


def set_host_enabled(hostname, enabled=True):
    context.session.assertPerm('host')
    host = get_host(hostname)
    if not host:
        raise koji.GenericError('host does not exist: %s' % hostname)

    update = UpdateProcessor('host_config', values=host, clauses=['host_id = %(id)i'])
    update.make_revoke()
    update.execute()

    fields = ('arches', 'capacity', 'description', 'comment', 'enabled')
    insert = InsertProcessor('host_config', data=dslice(host, fields))
    insert.set(host_id=host['id'], enabled=enabled)
    insert.make_create()
    insert.execute()


def add_host_to_channel(hostname, channel_name, create=False):
    """Add the host to the specified channel

    Channel must already exist unless create option is specified
    """
    context.session.assertPerm('host')
    host = get_host(hostname)
    if host is None:
        raise koji.GenericError('host does not exist: %s' % hostname)
    host_id = host['id']
    channel_id = get_channel_id(channel_name, create=create)
    if channel_id is None:
        raise koji.GenericError('channel does not exist: %s' % channel_name)
    channels = list_channels(host_id)
    for channel in channels:
        if channel['id'] == channel_id:
            raise koji.GenericError('host %s is already subscribed to the %s channel' %
                                    (hostname, channel_name))
    insert = InsertProcessor('host_channels')
    insert.set(host_id=host_id, channel_id=channel_id)
    insert.make_create()
    insert.execute()


def remove_host_from_channel(hostname, channel_name):
    """Remove the host from the specified channel

    :param str hostname: host name
    :param str channel_name: channel name
    """
    context.session.assertPerm('host')
    host = get_host(hostname)
    if host is None:
        raise koji.GenericError('host does not exist: %s' % hostname)
    host_id = host['id']
    channel_id = get_channel_id(channel_name)
    if channel_id is None:
        raise koji.GenericError('channel does not exist: %s' % channel_name)
    found = False
    channels = list_channels(host_id)
    for channel in channels:
        if channel['id'] == channel_id:
            found = True
            break
    if not found:
        raise koji.GenericError('host %s is not subscribed to the %s channel' %
                                (hostname, channel_name))

    values = {'host_id': host_id, 'channel_id': channel_id}
    clauses = ['host_id = %(host_id)i AND channel_id = %(channel_id)i']
    update = UpdateProcessor('host_channels', values=values, clauses=clauses)
    update.make_revoke()
    update.execute()


def rename_channel(old, new):
    """Rename a channel"""
    context.session.assertPerm('admin')
    if not isinstance(new, str):
        raise koji.GenericError("new channel name must be a string")
    cinfo = get_channel(old, strict=True)
    dup_check = get_channel(new, strict=False)
    if dup_check:
        raise koji.GenericError("channel %(name)s already exists (id=%(id)i)" % dup_check)
    update = UpdateProcessor('channels', clauses=['id=%(id)i'], values=cinfo)
    update.set(name=new)
    update.execute()


def remove_channel(channel_name, force=False):
    """Remove a channel

    Channel must have no hosts, unless force is set to True
    If a channel has associated tasks, it cannot be removed
    and an exception will be raised.

    Removing channel will remove also remove complete history
    for that channel.
    """
    context.session.assertPerm('admin')
    channel_id = get_channel_id(channel_name, strict=True)
    # check for task references
    query = QueryProcessor(tables=['task'], clauses=['channel_id=%(channel_id)i'],
                           values=locals(), columns=['id'], opts={'limit': 1})
    # XXX slow query
    if query.execute():
        raise koji.GenericError('channel %s has task references' % channel_name)
    query = QueryProcessor(tables=['host_channels'], clauses=['channel_id=%(channel_id)i'],
                           values=locals(), columns=['host_id'], opts={'limit': 1})
    if query.execute():
        if not force:
            raise koji.GenericError('channel %s has host references' % channel_name)
        delete = """DELETE FROM host_channels WHERE channel_id=%(channel_id)i"""
        _dml(delete, locals())
    delete = """DELETE FROM channels WHERE id=%(channel_id)i"""
    _dml(delete, locals())


def get_ready_hosts():
    """Return information about hosts that are ready to build.

    Hosts set the ready flag themselves
    Note: We ignore hosts that are late checking in (even if a host
        is busy with tasks, it should be checking in quite often).
    """
    c = context.cnx.cursor()
    fields = ('host.id', 'name', 'arches', 'task_load', 'capacity')
    aliases = ('id', 'name', 'arches', 'task_load', 'capacity')
    q = """
    SELECT %s FROM host
        JOIN sessions USING (user_id)
        JOIN host_config ON host.id = host_config.host_id
    WHERE enabled = TRUE AND ready = TRUE
        AND expired = FALSE
        AND master IS NULL
        AND update_time > NOW() - '5 minutes'::interval
        AND active IS TRUE
    """ % ','.join(fields)
    # XXX - magic number in query
    c.execute(q)
    hosts = [dict(zip(aliases, row)) for row in c.fetchall()]
    for host in hosts:
        q = """SELECT channel_id FROM host_channels WHERE host_id=%(id)s AND active IS TRUE"""
        c.execute(q, host)
        host['channels'] = [row[0] for row in c.fetchall()]
    return hosts


def get_all_arches():
    """Return a list of all (canonical) arches available from hosts"""
    ret = {}
    for (arches,) in _fetchMulti('SELECT arches FROM host_config WHERE active IS TRUE', {}):
        if arches is None:
            continue
        for arch in arches.split():
            # in a perfect world, this list would only include canonical
            # arches, but not all admins will undertand that.
            ret[koji.canonArch(arch)] = 1
    return to_list(ret.keys())


def get_active_tasks(host=None):
    """Return data on tasks that are yet to be run"""
    fields = ['id', 'state', 'channel_id', 'host_id', 'arch', 'method', 'priority', 'create_time']
    values = dslice(koji.TASK_STATES, ('FREE', 'ASSIGNED'))
    if host:
        values['arches'] = host['arches'].split() + ['noarch']
        values['channels'] = host['channels']
        values['host_id'] = host['id']
        clause = '(state = %(ASSIGNED)i AND host_id = %(host_id)i)'
        if values['channels']:
            clause += ''' OR (state = %(FREE)i AND arch IN %(arches)s \
AND channel_id IN %(channels)s)'''
        clauses = [clause]
    else:
        clauses = ['state IN (%(FREE)i,%(ASSIGNED)i)']
    queryOpts = {'limit': 100, 'order': 'priority,create_time'}
    query = QueryProcessor(columns=fields, tables=['task'], clauses=clauses,
                           values=values, opts=queryOpts)
    return query.execute()


def get_task_descendents(task, childMap=None, request=False):
    if childMap is None:
        childMap = {}
    children = task.getChildren(request=request)
    children.sort(key=lambda x: x['id'])
    # xmlrpclib requires dict keys to be strings
    childMap[str(task.id)] = children
    for child in children:
        get_task_descendents(Task(child['id']), childMap, request)
    return childMap


def maven_tag_archives(tag_id, event_id=None, inherit=True):
    """
    Get Maven artifacts associated with the given tag, following inheritance.
    For any parent tags where 'maven_include_all' is true, include all versions
    of a given groupId:artifactId, not just the most-recently-tagged.
    """
    packages = readPackageList(tagID=tag_id, event=event_id, inherit=True)
    taglist = [tag_id]
    if inherit:
        taglist.extend([link['parent_id'] for link in readFullInheritance(tag_id, event_id)])
    fields = [('tag.id', 'tag_id'), ('tag.name', 'tag_name'),
              ('build.pkg_id', 'pkg_id'), ('build.id', 'build_id'),
              ('package.name', 'build_name'), ('build.version', 'build_version'),
              ('build.release', 'build_release'), ('build.epoch', 'build_epoch'),
              ('build.state', 'state'), ('build.task_id', 'task_id'),
              ('build.owner', 'owner'),
              ('volume.id', 'volume_id'), ('volume.name', 'volume_name'),
              ('archiveinfo.id', 'id'), ('archiveinfo.type_id', 'type_id'),
              ('archiveinfo.buildroot_id', 'buildroot_id'),
              ('archiveinfo.filename', 'filename'), ('archiveinfo.size', 'size'),
              ('archiveinfo.checksum', 'checksum'),
              ('archiveinfo.checksum_type', 'checksum_type'),
              ('archiveinfo.metadata_only', 'metadata_only'),
              ('archiveinfo.extra', 'extra'),
              ('maven_archives.group_id', 'group_id'),
              ('maven_archives.artifact_id', 'artifact_id'),
              ('maven_archives.version', 'version'),
              ('tag_listing.create_event', 'tag_event')]
    tables = ['tag_listing']
    joins = ['tag ON tag_listing.tag_id = tag.id',
             'build ON tag_listing.build_id = build.id',
             'volume ON build.volume_id = volume.id',
             'package ON build.pkg_id = package.id',
             'archiveinfo ON build.id = archiveinfo.build_id',
             'maven_archives ON archiveinfo.id = maven_archives.archive_id']
    clauses = [eventCondition(event_id, 'tag_listing'), 'tag_listing.tag_id = %(tag_id)i']
    order = '-tag_event'
    query = QueryProcessor(tables=tables, joins=joins,
                           clauses=clauses, opts={'order': order},
                           transform=_fix_archive_row,
                           columns=[f[0] for f in fields],
                           aliases=[f[1] for f in fields])
    included = {}
    included_archives = set()
    # these indexes eat into the memory savings of the generator, but it's only
    # group_id/artifact_id/version/build_id/archive_id, which is much smaller than
    # the full query
    # ballpark estimate: 20-25% of total, less with heavy duplication of indexed values

    def _iter_archives():
        for tag_id in taglist:
            taginfo = get_tag(tag_id, strict=True, event=event_id)
            query.values['tag_id'] = tag_id
            archives = query.iterate()
            for archive in archives:
                pkg = packages.get(archive['pkg_id'])
                if not pkg or pkg['blocked']:
                    continue
                # 4 possibilities:
                # 1: we have never seen this group_id:artifact_id before
                #  - yield it, and add to the included dict
                # 2: we have seen the group_id:artifact_id before, but a different version
                #  - if the taginfo['maven_include_all'] is true, yield it and
                #    append it to the included_versions dict, otherwise skip it
                # 3: we have seen the group_id:artifact_id before, with the same version, from
                #    a different build
                #  - this is a different revision of the same GAV, ignore it because a more
                #    recently-tagged build has already been included
                # 4: we have seen the group_id:artifact_id before, with the same version, from
                #    the same build
                #  - it is another artifact from a build we're already including, so include it
                #    as well
                ga = '%(group_id)s:%(artifact_id)s' % archive
                included_versions = included.get(ga)
                if not included_versions:
                    included[ga] = {archive['version']: archive['build_id']}
                    included_archives.add(archive['id'])
                    yield archive
                    continue
                included_build = included_versions.get(archive['version'])
                if not included_build:
                    if taginfo['maven_include_all']:
                        included_versions[archive['version']] = archive['build_id']
                        included_archives.add(archive['id'])
                        yield archive
                    continue
                if included_build != archive['build_id']:
                    continue
                # make sure we haven't already seen this archive somewhere else in the
                # tag hierarchy
                if archive['id'] not in included_archives:
                    included_archives.add(archive['id'])
                    yield archive
    return _iter_archives()


def repo_init(tag, with_src=False, with_debuginfo=False, event=None, with_separate_src=False):
    """Create a new repo entry in the INIT state, return full repo data

    Returns a dictionary containing
        repo_id, event_id
    """
    logger = logging.getLogger("koji.hub.repo_init")
    state = koji.REPO_INIT
    tinfo = get_tag(tag, strict=True, event=event)
    koji.plugin.run_callbacks('preRepoInit', tag=tinfo, with_src=with_src,
                              with_debuginfo=with_debuginfo, event=event, repo_id=None,
                              with_separate_src=with_separate_src)
    tag_id = tinfo['id']
    repo_arches = {}
    if with_separate_src:
        repo_arches['src'] = 1
    if tinfo['arches']:
        for arch in tinfo['arches'].split():
            arch = koji.canonArch(arch)
            if arch in ['src', 'noarch']:
                continue
            repo_arches[arch] = 1
    repo_id = _singleValue("SELECT nextval('repo_id_seq')")
    if event is None:
        event_id = _singleValue("SELECT get_event()")
    else:
        # make sure event is valid
        q = "SELECT time FROM events WHERE id=%(event)s"
        event_time = _singleValue(q, locals(), strict=True)
        event_id = event
    insert = InsertProcessor('repo')
    insert.set(id=repo_id, create_event=event_id, tag_id=tag_id, state=state)
    insert.execute()
    # Need to pass event_id because even though this is a single transaction,
    # it is possible to see the results of other committed transactions
    latest = not tinfo['extra'].get('repo_include_all', False)
    # Note: the repo_include_all option is not recommended for common use
    #       see https://pagure.io/koji/issue/588 for background
    rpms, builds = readTaggedRPMS(tag_id, event=event_id, inherit=True, latest=latest)
    groups = readTagGroups(tag_id, event=event_id, inherit=True)
    blocks = [pkg for pkg in readPackageList(tag_id, event=event_id, inherit=True).values()
              if pkg['blocked']]
    repodir = koji.pathinfo.repo(repo_id, tinfo['name'])
    os.makedirs(repodir)  # should not already exist

    # generate comps and groups.spec
    groupsdir = "%s/groups" % (repodir)
    koji.ensuredir(groupsdir)
    comps = koji.generate_comps(groups, expand_groups=True)
    with open("%s/comps.xml" % groupsdir, 'w') as fo:
        fo.write(comps)

    # write repo info to disk
    repo_info = {
        'id': repo_id,
        'tag': tinfo['name'],
        'tag_id': tinfo['id'],
        'event_id': event_id,
        'with_src': with_src,
        'with_separate_src': with_separate_src,
        'with_debuginfo': with_debuginfo,
    }
    with open('%s/repo.json' % repodir, 'w') as fp:
        json.dump(repo_info, fp, indent=2)

    # get build dirs
    relpathinfo = koji.PathInfo(topdir='toplink')
    builddirs = {}
    for build in builds:
        relpath = relpathinfo.build(build)
        builddirs[build['id']] = relpath.lstrip('/')
    # generate pkglist files
    pkglist = {}
    for repoarch in repo_arches:
        archdir = joinpath(repodir, repoarch)
        koji.ensuredir(archdir)
        # Make a symlink to our topdir
        top_relpath = os.path.relpath(koji.pathinfo.topdir, archdir)
        top_link = joinpath(archdir, 'toplink')
        os.symlink(top_relpath, top_link)
        pkglist[repoarch] = open(joinpath(archdir, 'pkglist'), 'w')
    # NOTE - rpms is now an iterator
    for rpminfo in rpms:
        if not with_debuginfo and koji.is_debuginfo(rpminfo['name']):
            continue
        relpath = "%s/%s\n" % (builddirs[rpminfo['build_id']], relpathinfo.rpm(rpminfo))
        arch = rpminfo['arch']
        if arch == 'src':
            if with_src:
                for repoarch in repo_arches:
                    pkglist[repoarch].write(relpath)
            if with_separate_src:
                pkglist[arch].write(relpath)
        elif arch == 'noarch':
            for repoarch in repo_arches:
                if repoarch == 'src':
                    continue
                pkglist[repoarch].write(relpath)
        else:
            repoarch = koji.canonArch(arch)
            if repoarch not in repo_arches:
                # Do not create a repo for arches not in the arch list for this tag
                continue
            pkglist[repoarch].write(relpath)
    for repoarch in repo_arches:
        pkglist[repoarch].close()

    # write blocked package lists
    for repoarch in repo_arches:
        blocklist = open(joinpath(repodir, repoarch, 'blocklist'), 'w')
        for pkg in blocks:
            blocklist.write(pkg['package_name'])
            blocklist.write('\n')
        blocklist.close()

    if context.opts.get('EnableMaven') and tinfo['maven_support']:
        artifact_dirs = {}
        dir_links = set()
        for archive in maven_tag_archives(tinfo['id'], event_id):
            buildinfo = {'name': archive['build_name'],
                         'version': archive['build_version'],
                         'release': archive['build_release'],
                         'epoch': archive['build_epoch'],
                         'volume_name': archive['volume_name'],
                         }
            srcdir = joinpath(koji.pathinfo.mavenbuild(buildinfo),
                              koji.pathinfo.mavenrepo(archive))
            destlink = joinpath(repodir, 'maven',
                                koji.pathinfo.mavenrepo(archive))
            dir_links.add((srcdir, destlink))
            dest_parent = os.path.dirname(destlink)
            artifact_dirs.setdefault(dest_parent, set()).add((archive['group_id'],
                                                              archive['artifact_id'],
                                                              archive['version']))
        created_dirs = set()
        for srcdir, destlink in dir_links:
            dest_parent = os.path.dirname(destlink)
            if dest_parent not in created_dirs:
                koji.ensuredir(dest_parent)
                created_dirs.add(dest_parent)
            relpath = os.path.relpath(srcdir, dest_parent)
            try:
                os.symlink(relpath, destlink)
            except Exception:
                log_error('Error linking %s to %s' % (destlink, relpath))
        for artifact_dir, artifacts in artifact_dirs.items():
            _write_maven_repo_metadata(artifact_dir, artifacts)

    koji.plugin.run_callbacks('postRepoInit', tag=tinfo, with_src=with_src,
                              with_debuginfo=with_debuginfo, event=event, repo_id=repo_id,
                              with_separate_src=with_separate_src)
    return [repo_id, event_id]


def _write_maven_repo_metadata(destdir, artifacts):
    # Sort the list so that the highest version number comes last.
    # group_id and artifact_id should be the same for all entries,
    # so we're really only comparing versions.
    sort_param = {'key': functools.cmp_to_key(rpm.labelCompare)}
    artifacts = sorted(artifacts, **sort_param)
    artifactinfo = dict(zip(['group_id', 'artifact_id', 'version'], artifacts[-1]))
    artifactinfo['timestamp'] = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    contents = """<?xml version="1.0"?>
<metadata>
  <groupId>%(group_id)s</groupId>
  <artifactId>%(artifact_id)s</artifactId>
  <versioning>
    <latest>%(version)s</latest>
    <release>%(version)s</release>
    <versions>
""" % artifactinfo
    for artifact in artifacts:
        contents += """      <version>%s</version>
""" % artifact[2]
    contents += """    </versions>
    <lastUpdated>%s</lastUpdated>
  </versioning>
</metadata>
""" % datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    with open(joinpath(destdir, 'maven-metadata.xml'), 'w') as mdfile:
        mdfile.write(contents)
    _generate_maven_metadata(destdir)


def dist_repo_init(tag, keys, task_opts):
    """Create a new repo entry in the INIT state, return full repo data"""
    state = koji.REPO_INIT
    tinfo = get_tag(tag, strict=True)
    tag_id = tinfo['id']
    event = task_opts.get('event')
    volume = task_opts.get('volume')
    if volume is not None:
        volume = lookup_name('volume', volume, strict=True)['name']
    arches = list(set([koji.canonArch(a) for a in task_opts['arch']]))
    # note: we need to match args from the other preRepoInit callback
    koji.plugin.run_callbacks('preRepoInit', tag=tinfo, with_src=False,
                              with_debuginfo=False, event=event, repo_id=None,
                              dist=True, keys=keys, arches=arches, task_opts=task_opts,
                              with_separate_src=False)
    if not event:
        event = get_event()
    repo_id = nextval('repo_id_seq')
    insert = InsertProcessor('repo')
    insert.set(id=repo_id, create_event=event, tag_id=tag_id,
               state=state, dist=True)
    insert.execute()
    repodir = koji.pathinfo.distrepo(repo_id, tinfo['name'], volume=volume)
    for arch in arches:
        koji.ensuredir(joinpath(repodir, arch))
    if volume and volume != 'DEFAULT':
        # symlink from main volume to this one
        basedir = koji.pathinfo.distrepo(repo_id, tinfo['name'])
        relpath = os.path.relpath(repodir, os.path.dirname(basedir))
        koji.ensuredir(os.path.dirname(basedir))
        os.symlink(relpath, basedir)
    # handle comps
    if task_opts.get('comps'):
        groupsdir = joinpath(repodir, 'groups')
        koji.ensuredir(groupsdir)
        shutil.copyfile(joinpath(koji.pathinfo.work(),
                                 task_opts['comps']), groupsdir + '/comps.xml')
    # write repo info to disk
    repo_info = {
        'id': repo_id,
        'tag': tinfo['name'],
        'tag_id': tinfo['id'],
        'keys': keys,
        'volume': volume,
        'task_opts': task_opts,
    }
    with open('%s/repo.json' % repodir, 'w') as fp:
        json.dump(repo_info, fp, indent=2)
    # note: we need to match args from the other postRepoInit callback
    koji.plugin.run_callbacks('postRepoInit', tag=tinfo, with_src=False,
                              with_debuginfo=False, event=event, repo_id=repo_id,
                              dist=True, keys=keys, arches=arches, task_opts=task_opts,
                              repodir=repodir, with_reparate_src=False)
    return repo_id, event


def repo_set_state(repo_id, state, check=True):
    """Set repo state"""
    if check:
        # The repo states are sequential, going backwards makes no sense
        q = """SELECT state FROM repo WHERE id = %(repo_id)s FOR UPDATE"""
        oldstate = _singleValue(q, locals())
        if oldstate > state:
            raise koji.GenericError("Invalid repo state transition %s->%s"
                                    % (oldstate, state))
    q = """UPDATE repo SET state=%(state)s WHERE id = %(repo_id)s"""
    _dml(q, locals())


def repo_info(repo_id, strict=False):
    """Get repo information

    :param int repo_id: repo ID
    :param bool strict: raise an error on non-existent repo

    :returns: dict (id, state, create_event, creation_time, tag_id, tag_name,
              dist)
    """
    fields = (
        ('repo.id', 'id'),
        ('repo.state', 'state'),
        ('repo.create_event', 'create_event'),
        ('events.time', 'creation_time'),  # for compatibility with getRepo
        ('EXTRACT(EPOCH FROM events.time)', 'create_ts'),
        ('repo.tag_id', 'tag_id'),
        ('tag.name', 'tag_name'),
        ('repo.dist', 'dist'),
    )
    q = """SELECT %s FROM repo
    JOIN tag ON tag_id=tag.id
    JOIN events ON repo.create_event = events.id
    WHERE repo.id = %%(repo_id)s""" % ','.join([f[0] for f in fields])
    return _singleRow(q, locals(), [f[1] for f in fields], strict=strict)


def repo_ready(repo_id):
    """Set repo state to ready"""
    repo_set_state(repo_id, koji.REPO_READY)


def repo_expire(repo_id):
    """Set repo state to expired"""
    repo_set_state(repo_id, koji.REPO_EXPIRED)


def repo_problem(repo_id):
    """Set repo state to problem"""
    repo_set_state(repo_id, koji.REPO_PROBLEM)


def repo_delete(repo_id):
    """Attempt to mark repo deleted, return number of references

    If the number of references is nonzero, no change is made"""
    # get a row lock on the repo
    q = """SELECT state FROM repo WHERE id = %(repo_id)s FOR UPDATE"""
    _singleValue(q, locals())
    references = repo_references(repo_id)
    if not references:
        repo_set_state(repo_id, koji.REPO_DELETED)
    return len(references)


def repo_expire_older(tag_id, event_id, dist=None):
    """Expire repos for tag older than event

    If dist is not None, then only expire repos with the given dist value
    """
    st_ready = koji.REPO_READY
    clauses = ['tag_id = %(tag_id)s',
               'create_event < %(event_id)s',
               'state = %(st_ready)s']
    if dist is not None:
        dist = bool(dist)
        clauses.append('dist = %(dist)s')
    update = UpdateProcessor('repo', values=locals(), clauses=clauses)
    update.set(state=koji.REPO_EXPIRED)
    update.execute()


def repo_references(repo_id):
    """Return a list of buildroots that reference the repo"""
    fields = {
        'buildroot_id': 'id',
        'host_id': 'host_id',
        'create_event': 'create_event',
        'state': 'state'}
    fields, aliases = zip(*fields.items())
    values = {'repo_id': repo_id}
    clauses = ['repo_id=%(repo_id)s', 'retire_event IS NULL']
    query = QueryProcessor(columns=fields, aliases=aliases, tables=['standard_buildroot'],
                           clauses=clauses, values=values)
    # check results for bad states
    ret = []
    for data in query.execute():
        if data['state'] == koji.BR_STATES['EXPIRED']:
            log_error("Error: buildroot %(id)s expired, but has no retire_event" % data)
            continue
        ret.append(data)
    return ret


def get_active_repos():
    """Get data on all active repos

    This is a list of all the repos that the repo daemon needs to worry about.
    """
    fields = (
        ('repo.id', 'id'),
        ('repo.state', 'state'),
        ('repo.create_event', 'create_event'),
        ('EXTRACT(EPOCH FROM events.time)', 'create_ts'),
        ('repo.tag_id', 'tag_id'),
        ('repo.dist', 'dist'),
        ('tag.name', 'tag_name'),
    )
    fields, aliases = zip(*fields)
    values = {'st_deleted': koji.REPO_DELETED}
    joins = ['tag ON repo.tag_id=tag.id', 'events ON repo.create_event = events.id']
    clauses = ['repo.state != %(st_deleted)s']
    query = QueryProcessor(columns=fields, aliases=aliases, tables=['repo'],
                           joins=joins, clauses=clauses, values=values)
    return query.execute()


def tag_changed_since_event(event, taglist):
    """Report whether any changes since event affect any of the tags in list

    The function is used by the repo daemon to determine which of its repos
    are up to date.

    This function does not figure inheritance, the calling function should
    expand the taglist to include any desired inheritance.

    Returns: True or False
    """
    data = locals().copy()
    # first check the tag_updates table
    clauses = ['update_event > %(event)i', 'tag_id IN %(taglist)s']
    query = QueryProcessor(tables=['tag_updates'], columns=['id'],
                           clauses=clauses, values=data,
                           opts={'limit': 1})
    if query.execute():
        return True
    # also check these versioned tables
    tables = (
        'tag_listing',
        'tag_inheritance',
        'tag_config',
        'tag_packages',
        'tag_external_repos',
        'group_package_listing',
        'group_req_listing',
        'group_config',
    )
    clauses = ['create_event > %(event)i OR revoke_event > %(event)i',
               'tag_id IN %(taglist)s']
    for table in tables:
        query = QueryProcessor(tables=[table], columns=['tag_id'], clauses=clauses,
                               values=data, opts={'limit': 1})
        if query.execute():
            return True
    return False


def set_tag_update(tag_id, utype, event_id=None, user_id=None):
    """Record a non-versioned tag update"""
    utype_id = koji.TAG_UPDATE_TYPES.getnum(utype)
    if utype_id is None:
        raise koji.GenericError("Invalid update type: %s" % utype)
    if event_id is None:
        event_id = get_event()
    if user_id is None:
        context.session.assertLogin()
        user_id = context.session.user_id
    data = {'tag_id': tag_id, 'update_type': utype_id, 'update_event': event_id,
            'updater_id': user_id}
    insert = InsertProcessor('tag_updates', data=data)
    insert.execute()


def _validate_build_target_name(name):
    """ A helper function that validates a build target name. """
    max_name_length = 256
    if len(name) > max_name_length:
        raise koji.GenericError("Build target name %s is too long. Max length "
                                "is %s characters" % (name, max_name_length))


def create_build_target(name, build_tag, dest_tag):
    """Create a new build target"""

    context.session.assertPerm('target')
    return _create_build_target(name, build_tag, dest_tag)


def _create_build_target(name, build_tag, dest_tag):
    """Create a new build target(no access check)"""
    _validate_build_target_name(name)

    # Does a target with this name already exist?
    if get_build_targets(info=name):
        raise koji.GenericError("A build target with the name '%s' already exists" % name)

    # Does the build tag exist?
    build_tag_object = get_tag(build_tag)
    if not build_tag_object:
        raise koji.GenericError("build tag '%s' does not exist" % build_tag)
    build_tag = build_tag_object['id']

    # Does the dest tag exist?
    dest_tag_object = get_tag(dest_tag)
    if not dest_tag_object:
        raise koji.GenericError("destination tag '%s' does not exist" % dest_tag)
    dest_tag = dest_tag_object['id']

    # build targets are versioned, so if the target has previously been deleted, it
    # is possible the name is in the system
    id = get_build_target_id(name, create=True)

    insert = InsertProcessor('build_target_config')
    insert.set(build_target_id=id, build_tag=build_tag, dest_tag=dest_tag)
    insert.make_create()
    insert.execute()


def edit_build_target(buildTargetInfo, name, build_tag, dest_tag):
    """Set the build_tag and dest_tag of an existing build_target to new values"""
    context.session.assertPerm('target')
    _edit_build_target(buildTargetInfo, name, build_tag, dest_tag)


def _edit_build_target(buildTargetInfo, name, build_tag, dest_tag):
    """Edit build target parameters, w/ no access checks"""
    _validate_build_target_name(name)

    target = lookup_build_target(buildTargetInfo)
    if not target:
        raise koji.GenericError('invalid build target: %s' % buildTargetInfo)

    buildTargetID = target['id']

    build_tag_object = get_tag(build_tag)
    if not build_tag_object:
        raise koji.GenericError("build tag '%s' does not exist" % build_tag)
    buildTagID = build_tag_object['id']

    dest_tag_object = get_tag(dest_tag)
    if not dest_tag_object:
        raise koji.GenericError("destination tag '%s' does not exist" % dest_tag)
    destTagID = dest_tag_object['id']

    if target['name'] != name:
        # Allow renaming, for parity with tags
        id = _singleValue("""SELECT id from build_target where name = %(name)s""",
                          locals(), strict=False)
        if id is not None:
            raise koji.GenericError('name "%s" is already taken by build target %i' % (name, id))

        rename = """UPDATE build_target
        SET name = %(name)s
        WHERE id = %(buildTargetID)i"""

        _dml(rename, locals())

    update = UpdateProcessor('build_target_config', values=locals(),
                             clauses=["build_target_id = %(buildTargetID)i"])
    update.make_revoke()

    insert = InsertProcessor('build_target_config')
    insert.set(build_target_id=buildTargetID, build_tag=buildTagID, dest_tag=destTagID)
    insert.make_create()

    update.execute()
    insert.execute()


def delete_build_target(buildTargetInfo):
    """Delete the build target with the given name.  If no build target
    exists, raise a GenericError."""
    context.session.assertPerm('target')
    _delete_build_target(buildTargetInfo)


def _delete_build_target(buildTargetInfo):
    """Delete build target, no access checks"""
    target = lookup_build_target(buildTargetInfo)
    if not target:
        raise koji.GenericError('invalid build target: %s' % buildTargetInfo)

    targetID = target['id']

    # build targets are versioned, so we do not delete them from the db
    # instead we revoke the config entry
    update = UpdateProcessor('build_target_config', values=locals(),
                             clauses=["build_target_id = %(targetID)i"])
    update.make_revoke()
    update.execute()


def get_build_targets(info=None, event=None, buildTagID=None, destTagID=None, queryOpts=None):
    """Return data on all the build targets

    provide event to query at a different time"""
    fields = (
        ('build_target.id', 'id'),
        ('build_tag', 'build_tag'),
        ('dest_tag', 'dest_tag'),
        ('build_target.name', 'name'),
        ('tag1.name', 'build_tag_name'),
        ('tag2.name', 'dest_tag_name'),
    )
    joins = ['build_target ON build_target_config.build_target_id = build_target.id',
             'tag AS tag1 ON build_target_config.build_tag = tag1.id',
             'tag AS tag2 ON build_target_config.dest_tag = tag2.id']
    clauses = [eventCondition(event)]

    if info:
        if isinstance(info, str):
            clauses.append('build_target.name = %(info)s')
        elif isinstance(info, int):
            clauses.append('build_target.id = %(info)i')
        else:
            raise koji.GenericError('invalid type for lookup: %s' % type(info))
    if buildTagID is not None:
        clauses.append('build_tag = %(buildTagID)i')
    if destTagID is not None:
        clauses.append('dest_tag = %(destTagID)i')

    query = QueryProcessor(columns=[f[0] for f in fields], aliases=[f[1] for f in fields],
                           tables=['build_target_config'], joins=joins, clauses=clauses,
                           values=locals(), opts=queryOpts)
    return query.execute()


def get_build_target(info, event=None, strict=False):
    """Return the build target with the given name or ID.
    If there is no matching build target, return None."""
    targets = get_build_targets(info=info, event=event)
    if len(targets) == 1:
        return targets[0]
    elif strict:
        raise koji.GenericError('No matching build target found: %s' % info)
    else:
        return None


def lookup_name(table, info, strict=False, create=False):
    """Find the id and name in the table associated with info.

    Info can be the name to look up, or if create is false it can
    be the id.

    Return value is a dict with keys id and name, or None
    If there is no match, then the behavior depends on the options. If strict,
    then an error is raised. If create, then the required entry is created and
    returned.

    table should be the name of a table with (unique) fields
        id INTEGER
        name TEXT
    Any other fields should have default values, otherwise the
    create option will fail.
    """
    fields = ('id', 'name')
    if isinstance(info, int):
        q = """SELECT id,name FROM %s WHERE id=%%(info)d""" % table
    elif isinstance(info, str):
        q = """SELECT id,name FROM %s WHERE name=%%(info)s""" % table
    else:
        raise koji.GenericError('invalid type for id lookup: %s' % type(info))
    ret = _singleRow(q, locals(), fields, strict=False)
    if ret is None:
        if strict:
            raise koji.GenericError('No such entry in table %s: %s' % (table, info))
        elif create:
            if not isinstance(info, str):
                raise koji.GenericError('Name must be a string')
            id = _singleValue("SELECT nextval('%s_id_seq')" % table, strict=True)
            q = """INSERT INTO %s(id,name) VALUES (%%(id)i,%%(info)s)""" % table
            _dml(q, locals())
            return {'id': id, 'name': info}
        else:
            return ret
    return ret


def get_id(table, info, strict=False, create=False):
    """Find the id in the table associated with info."""
    data = lookup_name(table, info, strict, create)
    if data is None:
        return data
    else:
        return data['id']


def get_tag_id(info, strict=False, create=False):
    """Get the id for tag"""
    return get_id('tag', info, strict, create)


def lookup_tag(info, strict=False, create=False):
    """Get the id,name for tag"""
    return lookup_name('tag', info, strict, create)


def get_perm_id(info, strict=False, create=False):
    """Get the id for a permission"""
    return get_id('permissions', info, strict, create)


def lookup_perm(info, strict=False, create=False):
    """Get the id,name for perm"""
    return lookup_name('permissions', info, strict, create)


def get_package_id(info, strict=False, create=False):
    """Get the id for a package"""
    return get_id('package', info, strict, create)


def lookup_package(info, strict=False, create=False):
    """Get the id,name for package"""
    return lookup_name('package', info, strict, create)


def get_channel_id(info, strict=False, create=False):
    """Get the id for a channel"""
    return get_id('channels', info, strict, create)


def lookup_channel(info, strict=False, create=False):
    """Get the id,name for channel"""
    return lookup_name('channels', info, strict, create)


def get_group_id(info, strict=False, create=False):
    """Get the id for a group"""
    return get_id('groups', info, strict, create)


def lookup_group(info, strict=False, create=False):
    """Get the id,name for group"""
    return lookup_name('groups', info, strict, create)


def get_build_target_id(info, strict=False, create=False):
    """Get the id for a build target"""
    return get_id('build_target', info, strict, create)


def lookup_build_target(info, strict=False, create=False):
    """Get the id,name for build target"""
    return lookup_name('build_target', info, strict, create)


def create_tag(name, parent=None, arches=None, perm=None, locked=False, maven_support=False,
               maven_include_all=False, extra=None):
    """Create a new tag"""
    context.session.assertPerm('tag')
    return _create_tag(name, parent, arches, perm, locked, maven_support, maven_include_all, extra)


def _create_tag(name, parent=None, arches=None, perm=None, locked=False, maven_support=False,
                maven_include_all=False, extra=None):
    """Create a new tag, without access check"""

    max_name_length = 256
    if len(name) > max_name_length:
        raise koji.GenericError("Tag name %s is too long. Max length is %s characters",
                                name, max_name_length)

    arches = koji.parse_arches(arches, strict=True, allow_none=True)

    if not context.opts.get('EnableMaven') and (maven_support or maven_include_all):
        raise koji.GenericError("Maven support not enabled")

    # see if there is already a tag by this name (active)
    if get_tag(name):
        raise koji.GenericError("A tag with the name '%s' already exists" % name)

    # Does the parent exist?
    if parent:
        parent_tag = get_tag(parent)
        if not parent_tag:
            raise koji.GenericError("Parent tag '%s' could not be found" % parent)
        parent_id = parent_tag['id']
    else:
        parent_id = None

    # there may already be an id for a deleted tag, this will reuse it
    tag_id = get_tag_id(name, create=True)

    insert = InsertProcessor('tag_config')
    insert.set(tag_id=tag_id, arches=arches, perm_id=perm, locked=locked)
    insert.set(maven_support=maven_support, maven_include_all=maven_include_all)
    insert.make_create()
    insert.execute()

    # add extra data
    if extra is not None:
        for key, value in extra.items():
            data = {
                'tag_id': tag_id,
                'key': key,
                'value': json.dumps(value),
            }
            insert = InsertProcessor('tag_extra', data=data)
            insert.make_create()
            insert.execute()

    if parent_id:
        data = {'parent_id': parent_id,
                'priority': 0,
                'maxdepth': None,
                'intransitive': False,
                'noconfig': False,
                'pkg_filter': ''}
        _writeInheritanceData(tag_id, data)

    return tag_id


def get_tag(tagInfo, strict=False, event=None):
    """Get tag information based on the tagInfo.  tagInfo may be either
    a string (the tag name) or an int (the tag ID).
    Returns a map containing the following keys:

    - id :      unique id for the tag
    - name :    name of the tag
    - perm_id : permission id (may be null)
    - perm :    permission name (may be null)
    - arches :  tag arches (string, may be null)
    - locked :  lock setting (boolean)
    - maven_support :           maven support flag (boolean)
    - maven_include_all :       maven include all flag (boolean)
    - extra :   extra tag parameters (dictionary)

    If there is no tag matching the given tagInfo, and strict is False,
    return None.  If strict is True, raise a GenericError.

    Note that in order for a tag to 'exist', it must have an active entry
    in tag_config. A tag whose name appears in the tag table but has no
    active tag_config entry is considered deleted.
    """

    tables = ['tag_config']
    joins = ['tag ON tag.id = tag_config.tag_id',
             'LEFT OUTER JOIN permissions ON tag_config.perm_id = permissions.id']
    fields = {'tag.id': 'id',
              'tag.name': 'name',
              'tag_config.perm_id': 'perm_id',
              'permissions.name': 'perm',
              'tag_config.arches': 'arches',
              'tag_config.locked': 'locked',
              'tag_config.maven_support': 'maven_support',
              'tag_config.maven_include_all': 'maven_include_all'
              }
    clauses = [eventCondition(event, table='tag_config')]
    if isinstance(tagInfo, int):
        clauses.append("tag.id = %(tagInfo)i")
    elif isinstance(tagInfo, str):
        clauses.append("tag.name = %(tagInfo)s")
    else:
        raise koji.GenericError('invalid type for tagInfo: %s' % type(tagInfo))

    data = {'tagInfo': tagInfo}
    fields, aliases = zip(*fields.items())
    query = QueryProcessor(columns=fields, aliases=aliases, tables=tables,
                           joins=joins, clauses=clauses, values=data)
    result = query.executeOne()
    if not result:
        if strict:
            raise koji.GenericError("Invalid tagInfo: %r" % tagInfo)
        return None
    result['extra'] = get_tag_extra(result, event)
    return result


def get_tag_extra(tagInfo, event=None):
    """ Get tag extra info (no inheritance) """
    tables = ['tag_extra']
    fields = ['key', 'value']
    clauses = [eventCondition(event, table='tag_extra'), "tag_id = %(id)i"]
    query = QueryProcessor(columns=fields, tables=tables, clauses=clauses, values=tagInfo,
                           opts={'asList': True})
    result = {}
    for key, value in query.execute():
        value = parse_json(value, errstr="Invalid tag extra data: %s" % key)
        result[key] = value
    return result


def edit_tag(tagInfo, **kwargs):
    """Edit information for an existing tag.

    The tagInfo argument is the only required argument. After the tagInfo
    argument, specify any tag changes with additional keyword arguments.

    :param tagInfo: koji tag ID or name to edit (required).
    :type tagInfo: int or str

    :param str name: rename the tag.
    :param str arches: a space-separated list of arches for this tag.
    :param bool locked: whether this tag is locked or not.
    :param perm: the permission ID or name for this tag.
    :type perm: int, str, or None
    :param bool maven_support: whether Maven repos should be generated for the
                               tag.
    :param bool maven_include_all: include every build in this tag (including
                                   multiple versions of the same package) in
                                   the Maven repo.
    :param dict extra: add or update extra tag parameters.
    :param list remove_extra: remove extra tag parameters.
    """

    context.session.assertPerm('tag')
    _edit_tag(tagInfo, **kwargs)


def _edit_tag(tagInfo, **kwargs):
    """Edit information for an existing tag."""
    if not context.opts.get('EnableMaven') \
            and dslice(kwargs, ['maven_support', 'maven_include_all'], strict=False):
        raise koji.GenericError("Maven support not enabled")

    tag = get_tag(tagInfo, strict=True)
    if 'perm' in kwargs and 'perm_id' not in kwargs:
        # for compatibility, perm and perm_id are aliases
        # if both are given, perm_id takes precedence
        kwargs['perm_id'] = kwargs['perm']
    if 'perm_id' in kwargs:
        if kwargs['perm_id'] is not None:
            kwargs['perm_id'] = get_perm_id(kwargs['perm_id'], strict=True)

    name = kwargs.get('name')
    if name and tag['name'] != name:
        # attempt to update tag name
        # XXX - I'm not sure we should allow this sort of renaming anyway.
        # while I can see the convenience, it is an untracked change (granted
        # a cosmetic one). The more versioning-friendly way would be to create
        # a new tag with duplicate data and revoke the old tag. This is more
        # of a pain of course :-/  -mikem
        values = {
            'name': name,
            'tagID': tag['id']
        }
        q = """SELECT id FROM tag WHERE name=%(name)s"""
        id = _singleValue(q, values, strict=False)
        if id is not None:
            # new name is taken
            raise koji.GenericError("Name %s already taken by tag %s" % (name, id))
        update = """UPDATE tag
SET name = %(name)s
WHERE id = %(tagID)i"""
        _dml(update, values)

    # sanitize architecture names (space-separated string)
    arches = kwargs.get('arches')
    if arches and tag['arches'] != arches:
        kwargs['arches'] = koji.parse_arches(arches, strict=True, allow_none=True)

    # check for changes
    data = tag.copy()
    changed = False
    for key in ('perm_id', 'arches', 'locked', 'maven_support', 'maven_include_all'):
        if key in kwargs and data[key] != kwargs[key]:
            changed = True
            data[key] = kwargs[key]
    if changed:
        update = UpdateProcessor('tag_config', values=data, clauses=['tag_id = %(id)i'])
        update.make_revoke()
        update.execute()

        insert = InsertProcessor('tag_config', data=dslice(data, ('arches', 'perm_id', 'locked')))
        insert.set(tag_id=data['id'])
        insert.set(**dslice(data, ('maven_support', 'maven_include_all')))
        insert.make_create()
        insert.execute()

    # handle extra data
    if 'extra' in kwargs:
        # check whether one key is both in extra and remove_extra
        if 'remove_extra' in kwargs:
            for removed in kwargs['remove_extra']:
                if removed in kwargs['extra']:
                    raise koji.GenericError("Can not both add/update and remove tag-extra: '%s'" %
                                            removed)
        for key in kwargs['extra']:
            value = kwargs['extra'][key]
            if key not in tag['extra'] or tag['extra'][key] != value:
                data = {
                    'tag_id': tag['id'],
                    'key': key,
                    'value': json.dumps(kwargs['extra'][key]),
                }
                # revoke old entry, if any
                update = UpdateProcessor('tag_extra', values=data, clauses=['tag_id = %(tag_id)i',
                                                                            'key=%(key)s'])
                update.make_revoke()
                update.execute()
                # add new entry
                insert = InsertProcessor('tag_extra', data=data)
                insert.make_create()
                insert.execute()

    # handle remove_extra data
    if 'remove_extra' in kwargs:
        ne = [e for e in kwargs['remove_extra'] if e not in tag['extra']]
        if ne:
            raise koji.GenericError("Tag: %s doesn't have extra: %s" %
                                    (tag['name'], ', '.join(ne)))
        for key in kwargs['remove_extra']:
            data = {
                'tag_id': tag['id'],
                'key': key,
            }
            # revoke old entry
            update = UpdateProcessor('tag_extra', values=data, clauses=['tag_id = %(tag_id)i',
                                                                        'key=%(key)s'])
            update.make_revoke()
            update.execute()


def old_edit_tag(tagInfo, name, arches, locked, permissionID, extra=None):
    """Edit information for an existing tag."""
    return edit_tag(tagInfo, name=name, arches=arches, locked=locked,
                    perm_id=permissionID, extra=extra)


def delete_tag(tagInfo):
    """Delete the specified tag."""
    context.session.assertPerm('tag')
    _delete_tag(tagInfo)


def _delete_tag(tagInfo):
    """Delete the specified tag."""

    # We do not ever DELETE tag data. It is versioned -- we revoke it instead.

    def _tagDelete(tableName, value, columnName='tag_id'):
        update = UpdateProcessor(tableName, clauses=["%s = %%(value)i" % columnName],
                                 values={'value': value})
        update.make_revoke()
        update.execute()

    tag = get_tag(tagInfo, strict=True)
    tagID = tag['id']

    _tagDelete('tag_config', tagID)
    # technically, to 'delete' the tag we only have to revoke the tag_config entry
    # these remaining revocations are more for cleanup.
    _tagDelete('tag_extra', tagID)
    _tagDelete('tag_inheritance', tagID)
    _tagDelete('tag_inheritance', tagID, 'parent_id')
    _tagDelete('build_target_config', tagID, 'build_tag')
    _tagDelete('build_target_config', tagID, 'dest_tag')
    _tagDelete('tag_listing', tagID)
    _tagDelete('tag_packages', tagID)
    _tagDelete('tag_package_owners', tagID)
    _tagDelete('tag_external_repos', tagID)
    _tagDelete('group_config', tagID)
    _tagDelete('group_req_listing', tagID)
    _tagDelete('group_package_listing', tagID)
    # note: we do not delete the entry in the tag table (we can't actually, it
    # is still referenced by the revoked rows).
    # note: there is no need to do anything with the repo entries that reference tagID


def get_external_repo_id(info, strict=False, create=False):
    """Get the id for a build target"""
    return get_id('external_repo', info, strict, create)


def create_external_repo(name, url):
    """Create a new external repo with the given name and url.
    Return a map containing the id, name, and url
    of the new repo."""

    context.session.assertPerm('admin')

    if get_external_repos(info=name):
        raise koji.GenericError('An external repo named "%s" already exists' % name)

    id = get_external_repo_id(name, create=True)
    if not url.endswith('/'):
        # Ensure the url always ends with /
        url += '/'
    values = {'id': id, 'name': name, 'url': url}
    insert = InsertProcessor('external_repo_config')
    insert.set(external_repo_id=id, url=url)
    insert.make_create()
    insert.execute()
    return values


def get_external_repos(info=None, url=None, event=None, queryOpts=None):
    """Get a list of external repos.  If info is not None it may be a
    string (name) or an integer (id).
    If url is not None, filter the list of repos to those matching the
    given url."""
    fields = ['id', 'name', 'url']
    tables = ['external_repo']
    joins = ['external_repo_config ON external_repo_id = id']
    clauses = [eventCondition(event)]
    if info is not None:
        if isinstance(info, str):
            clauses.append('name = %(info)s')
        elif isinstance(info, int):
            clauses.append('id = %(info)i')
        else:
            raise koji.GenericError('invalid type for lookup: %s' % type(info))
    if url:
        clauses.append('url = %(url)s')

    query = QueryProcessor(columns=fields, tables=tables,
                           joins=joins, clauses=clauses,
                           values=locals(), opts=queryOpts)
    return query.execute()


def get_external_repo(info, strict=False, event=None):
    """
    Get information about a single external repository.

    :param info: a string (name) or an integer (id).
    :param bool strict: If True, raise an error if we found no matching
                        repository. If False, simply return None if we found
                        no matching repository. If unspecified, the default
                        value is False.
    :param int event: The event ID at which to search. If unspecified, the
                      default behavior is to search for the "active" repo
                      settings.
    :returns: a map containing the id, name, and url of the repository.
    """
    repos = get_external_repos(info, event=event)
    if repos:
        return repos[0]
    else:
        if strict:
            raise koji.GenericError('invalid repo info: %s' % info)
        else:
            return None


def edit_external_repo(info, name=None, url=None):
    """Edit an existing external repo"""

    context.session.assertPerm('admin')

    repo = get_external_repo(info, strict=True)
    repo_id = repo['id']

    if name and name != repo['name']:
        existing_id = _singleValue("""SELECT id FROM external_repo WHERE name = %(name)s""",
                                   locals(), strict=False)
        if existing_id is not None:
            raise koji.GenericError('name "%s" is already taken by external repo %i' %
                                    (name, existing_id))

        rename = """UPDATE external_repo SET name = %(name)s WHERE id = %(repo_id)i"""
        _dml(rename, locals())

    if url and url != repo['url']:
        if not url.endswith('/'):
            # Ensure the url always ends with /
            url += '/'

        update = UpdateProcessor('external_repo_config', values=locals(),
                                 clauses=['external_repo_id = %(repo_id)i'])
        update.make_revoke()

        insert = InsertProcessor('external_repo_config')
        insert.set(external_repo_id=repo_id, url=url)
        insert.make_create()

        update.execute()
        insert.execute()


def delete_external_repo(info):
    """
    Remove an external repository for any tags and delete it.

    :param info: external repository name or ID number
    :raises: GenericError if the repository does not exist.
    """

    context.session.assertPerm('admin')

    repo = get_external_repo(info, strict=True)
    repo_id = repo['id']

    for tag_repo in get_tag_external_repos(repo_info=repo['id']):
        remove_external_repo_from_tag(tag_info=tag_repo['tag_id'],
                                      repo_info=repo_id)

    update = UpdateProcessor('external_repo_config', values=locals(),
                             clauses=['external_repo_id = %(repo_id)i'])
    update.make_revoke()
    update.execute()


def add_external_repo_to_tag(tag_info, repo_info, priority, merge_mode='koji'):
    """Add an external repo to a tag"""

    context.session.assertPerm('tag')

    # sanity check for None value, which may happen if DB schema isn't updated to 1.21+
    if merge_mode is None:
        merge_mode = 'koji'
    if merge_mode not in koji.REPO_MERGE_MODES:
        raise koji.GenericError('Invalid merge mode: %s' % merge_mode)

    tag = get_tag(tag_info, strict=True)
    tag_id = tag['id']
    repo = get_external_repo(repo_info, strict=True)
    repo_id = repo['id']

    tag_repos = get_tag_external_repos(tag_info=tag_id)
    if [tr for tr in tag_repos if tr['external_repo_id'] == repo_id]:
        raise koji.GenericError('tag %s already associated with external repo %s' %
                                (tag['name'], repo['name']))
    if [tr for tr in tag_repos if tr['priority'] == priority]:
        raise koji.GenericError('tag %s already associated with an external repo at priority %i' %
                                (tag['name'], priority))

    insert = InsertProcessor('tag_external_repos')
    insert.set(tag_id=tag_id, external_repo_id=repo_id, priority=priority,
               merge_mode=merge_mode)
    insert.make_create()
    insert.execute()


def remove_external_repo_from_tag(tag_info, repo_info):
    """Remove an external repo from a tag"""

    context.session.assertPerm('tag')

    tag = get_tag(tag_info, strict=True)
    tag_id = tag['id']
    repo = get_external_repo(repo_info, strict=True)
    repo_id = repo['id']

    if not get_tag_external_repos(tag_info=tag_id, repo_info=repo_id):
        raise koji.GenericError('external repo %s not associated with tag %s' %
                                (repo['name'], tag['name']))

    update = UpdateProcessor('tag_external_repos', values=locals(),
                             clauses=["tag_id = %(tag_id)i", "external_repo_id = %(repo_id)i"])
    update.make_revoke()
    update.execute()


def edit_tag_external_repo(tag_info, repo_info, priority=None, merge_mode=None):
    """Edit a tag<->external repo association
    This allows you to update the priority and merge_mode without removing/adding the repo.

    Note that None value of priority and merge_mode means no change on it
    """

    context.session.assertPerm('tag')

    tag = get_tag(tag_info, strict=True)
    tag_id = tag['id']
    repo = get_external_repo(repo_info, strict=True)
    repo_id = repo['id']

    tag_repos = get_tag_external_repos(tag_info=tag_id, repo_info=repo_id)
    if not tag_repos:
        raise koji.GenericError('external repo %s not associated with tag %s' %
                                (repo['name'], tag['name']))
    tag_repo = tag_repos[0]

    data = {}
    for k in ('priority', 'merge_mode'):
        val = locals().get(k)
        # None value means no change
        if val is not None and val != tag_repo[k]:
            data[k] = val
    if not data:
        return False
    else:
        for k in ('priority', 'merge_mode'):
            data.setdefault(k, tag_repo[k])
        remove_external_repo_from_tag(tag_id, repo_id)
        add_external_repo_to_tag(tag_id, repo_id, **data)
        return True


def get_tag_external_repos(tag_info=None, repo_info=None, event=None):
    """
    Get a list of tag<->external repo associations.

    The list of associations is ordered by the priority field.

    Each map containing the following fields:
      tag_id
      tag_name
      external_repo_id
      external_repo_name
      url
      merge_mode
      priority

    :param tag_info: Tag name or ID number. This field is optional. If you
                     specify a value here, Koji will only return
                     repo association information for this single tag.
    :param repo_info: External repository name or ID number. This field is
                      optional. If you specify a value here, Koji will only
                      return tag association information for this single
                      repository.
    :param int event: The event ID at which to search. If unspecified, the
                      default behavior is to search for the "active" tag and
                      repo settings.
    """
    tables = ['tag_external_repos']
    joins = ['tag ON tag_external_repos.tag_id = tag.id',
             'external_repo ON tag_external_repos.external_repo_id = external_repo.id',
             'external_repo_config ON external_repo.id = external_repo_config.external_repo_id']
    fields = {
        'external_repo.id': 'external_repo_id',
        'external_repo.name': 'external_repo_name',
        'priority': 'priority',
        'tag.id': 'tag_id',
        'tag.name': 'tag_name',
        'url': 'url',
        'merge_mode': 'merge_mode',
    }
    columns, aliases = zip(*fields.items())

    clauses = [eventCondition(event, table='tag_external_repos'),
               eventCondition(event, table='external_repo_config')]
    if tag_info:
        tag = get_tag(tag_info, strict=True, event=event)
        tag_id = tag['id']
        clauses.append('tag.id = %(tag_id)i')
    if repo_info:
        repo = get_external_repo(repo_info, strict=True, event=event)
        repo_id = repo['id']
        clauses.append('external_repo.id = %(repo_id)i')

    opts = {'order': 'priority'}

    query = QueryProcessor(tables=tables, joins=joins,
                           columns=columns, aliases=aliases,
                           clauses=clauses, values=locals(),
                           opts=opts)
    return query.execute()


def get_external_repo_list(tag_info, event=None):
    """
    Get an ordered list of all external repos associated with the tags in the
    hierarchy rooted at the specified tag.  External repos will be returned
    depth-first, and ordered by priority for each tag.  Duplicates will be
    removed.  Returns a list of maps containing the following fields:

    tag_id
    tag_name
    external_repo_id
    external_repo_name
    url
    merge_mode
    priority
    """
    tag = get_tag(tag_info, strict=True, event=event)
    tag_list = [tag['id']]
    for parent in readFullInheritance(tag['id'], event):
        tag_list.append(parent['parent_id'])
    seen_repos = {}
    repos = []
    for tag_id in tag_list:
        for tag_repo in get_tag_external_repos(tag_info=tag_id, event=event):
            if tag_repo['external_repo_id'] not in seen_repos:
                repos.append(tag_repo)
                seen_repos[tag_repo['external_repo_id']] = 1
    return repos


def get_user(userInfo=None, strict=False, krb_princs=True):
    """Return information about a user.

    :param userInfo: a str (Kerberos principal or name) or an int (user id)
                     or a dict:
                         - id: User's ID
                         - name: User's name
                         - krb_principal: Kerberos principal
    :param bool strict: whether raising Error when no user found
    :param bool krb_princs: whether show krb_principals in result
    :return: a dict as user's information:
        id: user id
        name: user name
        status: user status (int), may be null
        usertype: user type (int), 0 person, 1 for host, may be null
        krb_principals: the user's Kerberos principals (list)
    """
    if userInfo is None:
        userInfo = context.session.user_id
        if userInfo is None:
            # not logged in
            raise koji.GenericError("No user provided")
    fields = ['id', 'name', 'status', 'usertype']
    if isinstance(userInfo, dict):
        data = userInfo
    elif isinstance(userInfo, int):
        data = {'id': userInfo}
    elif isinstance(userInfo, str):
        data = {'info': userInfo}
        clauses = ['krb_principal = %(info)s OR name = %(info)s']
    else:
        raise koji.GenericError('invalid type for userInfo: %s'
                                % type(userInfo))
    if isinstance(data, dict) and not data.get('info'):
        clauses = []
        uid = data.get('id')
        if uid is not None:
            if isinstance(uid, int):
                clauses.append('users.id = %(id)i')
            else:
                raise koji.GenericError('invalid type for userid: %s'
                                        % type(uid))
        username = data.get('name')
        if username:
            if isinstance(username, str):
                clauses.append('users.name = %(name)s')
            else:
                raise koji.GenericError('invalid type for username: %s'
                                        % type(username))
        krb_principal = data.get('krb_principal')
        if krb_principal:
            if isinstance(krb_principal, str):
                clauses.append('user_krb_principals.krb_principal'
                               ' = %(krb_principal)s')
            else:
                raise koji.GenericError('invalid type for krb_principal: %s'
                                        % type(krb_principal))

    query = QueryProcessor(tables=['users'], columns=fields,
                           joins=['LEFT JOIN user_krb_principals'
                                  ' ON users.id = user_krb_principals.user_id'],
                           clauses=clauses, values=data)
    user = query.executeOne()
    if not user and strict:
        raise koji.GenericError("No such user: %r" % userInfo)
    if user and krb_princs:
        user['krb_principals'] = list_user_krb_principals(user['id'])
    return user


def edit_user(userInfo, name=None, krb_principal_mappings=None):
    """Edit information for an existing user.

    Use this method to rename a user, or to add/remove/modify Kerberos
    principal(s) for this account.

    Example krb_principal_mappings values:

    To add a new Kerberos principal to a user account:
      [{'old': None, 'new': 'myuser@NEW.EXAMPLE.COM'}]

    To remove an old Kerberos principal from a user account:
      [{'old': 'myuser@OLD.EXAMPLE.COM', 'new': None}]

    To modify a user's old Kerberos principal to a new one:
      [{'old': 'myuser@OLD.EXAMPLE.NET', 'new': 'myuser@NEW.EXAMPLE.NET'}]

    :param userInfo: username (str) or ID (int)
    :param str name: new name for this user account
    :param list krb_principal_mappings: List of changes to make for this
                                        user's Kerberos principal. Each change
                                        is a dict of "old" and "new"
                                        Kerberos principals.
    :raises: GenericError if the user does not exist, or if there were
             problems in the krb_principal_mappings.
    """

    context.session.assertPerm('admin')
    _edit_user(userInfo, name=name,
               krb_principal_mappings=krb_principal_mappings)


def _edit_user(userInfo, name=None, krb_principal_mappings=None):
    """Edit information for an existing user."""
    user = get_user(userInfo, strict=True)
    if name and user['name'] != name:
        # attempt to update user name
        values = {
            'name': name,
            'userID': user['id']
        }
        q = """SELECT id FROM users WHERE name=%(name)s"""
        id = _singleValue(q, values, strict=False)
        if id is not None:
            # new name is taken
            raise koji.GenericError("Name %s already taken by user %s" % (name, id))
        update = UpdateProcessor('users',
                                 values={'userID': user['id']},
                                 clauses=['id = %(userID)i'])
        update.set(name=name)
        update.execute()
    if krb_principal_mappings:
        added = set()
        removed = set()
        for pairs in krb_principal_mappings:
            old = pairs.get('old')
            new = pairs.get('new')
            if old:
                removed.add(old)
            if new:
                added.add(new)
        dups = added & removed
        if dups:
            raise koji.GenericError("There are some conflicts between added"
                                    " and removed Kerberos principals: %s"
                                    % ', '.join(dups))
        currents = set(user.get('krb_principals'))
        dups = added & currents
        if dups:
            raise koji.GenericError("Cannot add existing Kerberos"
                                    " principals: %s" % ', '.join(dups))
        unable_removed = removed - currents
        if unable_removed:
            raise koji.GenericError("Cannot remove non-existent Kerberos"
                                    " principals: %s"
                                    % ', '.join(unable_removed))

        # attempt to update kerberos principal
        for r in removed:
            context.session.removeKrbPrincipal(user['id'], krb_principal=r)
        for a in added:
            context.session.setKrbPrincipal(user['id'], krb_principal=a)


def list_user_krb_principals(user_info=None):
    """Return kerberos principal list of a user.

    :param user_info: either a str (username) or an int (user id)
    :return: user's kerberos principals (list)
    """
    if user_info is None:
        user_info = context.session.user_id
        if user_info is None:
            # not logged in
            raise koji.GenericError("No user provided")
    fields = ['krb_principal']
    data = {'info': user_info}
    if isinstance(user_info, int):
        joins = []
        clauses = ['user_id = %(info)i']
    elif isinstance(user_info, str):
        joins = ['users ON users.id = user_krb_principals.user_id']
        clauses = ['name = %(info)s']
    else:
        raise koji.GenericError('invalid type for user_info: %s'
                                % type(user_info))
    query = QueryProcessor(tables=['user_krb_principals'],
                           columns=fields, joins=joins,
                           clauses=clauses, values=data,
                           transform=lambda row: row['krb_principal'])
    return query.execute() or []


def get_user_by_krb_principal(krb_principal, strict=False, krb_princs=True):
    """get information about a user by kerberos principal.

    :param str krb_principal: full user kerberos principals
    :param bool strict: whether raising Error when no user found
    :param bool krb_princs: whether show krb_principals in result
    :return: a dict as user's information:
        id: user id
        name: user name
        status: user status (int), may be null
        usertype: user type (int), 0 person, 1 for host, may be null
        krb_principals: the user's Kerberos principals (list)
    """
    if krb_principal is None:
        raise koji.GenericError("No kerberos principal provided")
    if not isinstance(krb_principal, str):
        raise koji.GenericError("invalid type for krb_principal: %s"
                                % type(krb_principal))
    return get_user({'krb_principal': krb_principal}, strict=strict,
                    krb_princs=krb_princs)


def find_build_id(X, strict=False):
    """gets build ID for various inputs

    :param int|str|dict X: build ID | NVR | dict with name, version and release values

    :returns int: build ID
    """
    if isinstance(X, int):
        return X
    elif isinstance(X, str):
        data = koji.parse_NVR(X)
    elif isinstance(X, dict):
        data = X
    else:
        raise koji.GenericError("Invalid argument: %r" % X)

    if not ('name' in data and 'version' in data and 'release' in data):
        raise koji.GenericError('did not provide name, version, and release')

    c = context.cnx.cursor()
    q = """SELECT build.id FROM build JOIN package ON build.pkg_id=package.id
    WHERE package.name=%(name)s AND build.version=%(version)s
    AND build.release=%(release)s
    """
    # contraints should ensure this is unique
    # log_error(koji.db._quoteparams(q,data))
    c.execute(q, data)
    r = c.fetchone()
    # log_error("%r" % r )
    if not r:
        if strict:
            raise koji.GenericError('No matching build found: %r' % X)
        else:
            return None
    return r[0]


def get_build(buildInfo, strict=False):
    """Return information about a build.

    buildID may be either a int ID, a string NVR, or a map containing
    'name', 'version' and 'release.

    A map will be returned containing the following keys*:
      id: build ID
      package_id: ID of the package built
      package_name: name of the package built
      name: same as package_name
      version
      release
      epoch
      nvr
      state
      task_id: ID of the task that kicked off the build
      owner_id: ID of the user who kicked off the build
      owner_name: name of the user who kicked off the build
      volume_id: ID of the storage volume
      volume_name: name of the storage volume
      creation_event_id: id of the create_event
      creation_time: time the build was created (text)
      creation_ts: time the build was created (epoch)
      start_time: time the build was started (may be null)
      start_ts: time the build was started (epoch, may be null)
      completion_time: time the build was completed (may be null)
      completion_ts: time the build was completed (epoch, may be null)
      source: the SCM URL of the sources used in the build -
              dereferenced git hash is stored here
      extra: dictionary with extra data about the build
          - source:
              - original_url: while build.source contains concrete
                SCM hash, this field can contain SCM url which was
                used when launching build (e.g. git_url#master)
      cg_id: ID of CG which reserved or imported this build
      cg_name: name of CG which reserved or imported this build

    If there is no build matching the buildInfo given, and strict is specified,
    raise an error.  Otherwise return None.

    [*] Not every build will have data for all keys. E.g. not all builds will
        associated task ids, and not all import methods provide source info.
    """
    buildID = find_build_id(buildInfo, strict=strict)
    if buildID is None:
        return None

    fields = (('build.id', 'id'), ('build.version', 'version'), ('build.release', 'release'),
              ('build.id', 'build_id'),
              ('build.epoch', 'epoch'), ('build.state', 'state'),
              ('build.completion_time', 'completion_time'),
              ('build.start_time', 'start_time'),
              ('build.task_id', 'task_id'),
              ('events.id', 'creation_event_id'), ('events.time', 'creation_time'),
              ('package.id', 'package_id'), ('package.name', 'package_name'),
              ('package.name', 'name'),
              ('volume.id', 'volume_id'), ('volume.name', 'volume_name'),
              ("package.name || '-' || build.version || '-' || build.release", 'nvr'),
              ('EXTRACT(EPOCH FROM events.time)', 'creation_ts'),
              ('EXTRACT(EPOCH FROM build.start_time)', 'start_ts'),
              ('EXTRACT(EPOCH FROM build.completion_time)', 'completion_ts'),
              ('users.id', 'owner_id'), ('users.name', 'owner_name'),
              ('build.cg_id', 'cg_id'),
              ('build.source', 'source'),
              ('build.extra', 'extra'))
    fields, aliases = zip(*fields)
    joins = ['events ON build.create_event = events.id',
             'package on build.pkg_id = package.id',
             'volume on build.volume_id = volume.id',
             'users on build.owner = users.id',
             ]
    clauses = ['build.id = %(buildID)i']
    query = QueryProcessor(columns=fields, aliases=aliases, values=locals(),
                           transform=_fix_extra_field,
                           tables=['build'], joins=joins, clauses=clauses)
    result = query.executeOne()

    if not result:
        if strict:
            raise koji.GenericError('No matching build found: %s' % buildInfo)
        else:
            return None
    if result['cg_id']:
        result['cg_name'] = lookup_name('content_generator', result['cg_id'], strict=True)['name']
    else:
        result['cg_name'] = None
    return result


def get_build_logs(build):
    """Return a list of log files for the given build"""
    buildinfo = get_build(build, strict=True)
    logdir = koji.pathinfo.build_logs(buildinfo)
    logreldir = os.path.relpath(logdir, koji.pathinfo.topdir)
    if not os.path.exists(logdir):
        return []
    if not os.path.isdir(logdir):
        raise koji.GenericError("Not a directory: %s" % logdir)
    logs = []
    for dirpath, dirs, files in os.walk(logdir):
        subdir = os.path.relpath(dirpath, logdir)
        for fn in files:
            filepath = joinpath(dirpath, fn)
            if os.path.islink(filepath):
                logger.warning("Symlink under logdir: %s", filepath)
                continue
            if not os.path.isfile(filepath):
                logger.warning("Non-regular file under logdir: %s", filepath)
                continue
            loginfo = {
                'name': fn,
                'dir': subdir,
                'path': "%s/%s/%s" % (logreldir, subdir, fn)
            }
            logs.append(loginfo)
    return logs


def get_next_release(build_info):
    """find the last successful or deleted build of this N-V. If building is
    specified, skip also builds in progress"""
    values = {
        'name': build_info['name'],
        'version': build_info['version'],
        'states': (
            koji.BUILD_STATES['COMPLETE'],
            koji.BUILD_STATES['DELETED'],
            koji.BUILD_STATES['BUILDING']
        )
    }
    query = QueryProcessor(tables=['build'], joins=['package ON build.pkg_id = package.id'],
                           columns=['build.id', 'release'],
                           clauses=['name = %(name)s', 'version = %(version)s',
                                    'state in %(states)s'],
                           values=values,
                           opts={'order': '-build.id', 'limit': 1})
    result = query.executeOne()
    release = None
    if result:
        release = result['release']

    if not release:
        release = '1'
    elif release.isdigit():
        release = str(int(release) + 1)
    elif len(release.split('.')) == 2 and release.split('.')[0].isdigit():
        # Handle the N.%{dist} case
        r_split = release.split('.')
        r_split[0] = str(int(r_split[0]) + 1)
        release = '.'.join(r_split)
    else:
        raise koji.BuildError('Unable to increment release value: %s' % release)
    return release


def _fix_rpm_row(row):
    if 'extra' in row:
        row['extra'] = parse_json(row['extra'], desc='rpm extra')
    return row


# alias for now, may change in the future
_fix_archive_row = _fix_rpm_row


def get_rpm(rpminfo, strict=False, multi=False):
    """Get information about the specified RPM

    rpminfo may be any one of the following:
    - a int ID
    - a string N-V-R.A
    - a string N-V-R.A@location
    - a map containing 'name', 'version', 'release', and 'arch'
      (and optionally 'location')

    If specified, location should match the name of an external repo

    A map will be returned, with the following keys:
    - id
    - name
    - version
    - release
    - arch
    - epoch
    - payloadhash
    - size
    - buildtime
    - build_id
    - buildroot_id
    - external_repo_id
    - external_repo_name
    - metadata_only
    - extra

    If there is no RPM with the given ID, None is returned, unless strict
    is True in which case an exception is raised

    If more than one RPM matches, and multi is True, then a list of results is
    returned. If multi is False, a single match is returned (an internal one if
    possible).
    """
    fields = (
        ('rpminfo.id', 'id'),
        ('build_id', 'build_id'),
        ('buildroot_id', 'buildroot_id'),
        ('rpminfo.name', 'name'),
        ('version', 'version'),
        ('release', 'release'),
        ('epoch', 'epoch'),
        ('arch', 'arch'),
        ('external_repo_id', 'external_repo_id'),
        ('external_repo.name', 'external_repo_name'),
        ('payloadhash', 'payloadhash'),
        ('size', 'size'),
        ('buildtime', 'buildtime'),
        ('metadata_only', 'metadata_only'),
        ('extra', 'extra'),
    )
    # we can look up by id or NVRA
    data = None
    if isinstance(rpminfo, int):
        data = {'id': rpminfo}
    elif isinstance(rpminfo, str):
        data = koji.parse_NVRA(rpminfo)
    elif isinstance(rpminfo, dict):
        data = rpminfo.copy()
    else:
        raise koji.GenericError("Invalid argument: %r" % rpminfo)
    clauses = []
    if 'id' in data:
        clauses.append("rpminfo.id=%(id)s")
    else:
        clauses.append("""rpminfo.name=%(name)s AND version=%(version)s
        AND release=%(release)s AND arch=%(arch)s""")
    retry = False
    if 'location' in data:
        data['external_repo_id'] = get_external_repo_id(data['location'], strict=True)
        clauses.append("""external_repo_id = %(external_repo_id)i""")
    elif not multi:
        # try to match internal first, otherwise first matching external
        retry = True  # if no internal match
        orig_clauses = list(clauses)  # copy
        clauses.append("""external_repo_id = 0""")

    joins = ['external_repo ON rpminfo.external_repo_id = external_repo.id']

    query = QueryProcessor(columns=[f[0] for f in fields], aliases=[f[1] for f in fields],
                           tables=['rpminfo'], joins=joins, clauses=clauses,
                           values=data, transform=_fix_rpm_row)
    if multi:
        return query.execute()
    ret = query.executeOne()
    if ret:
        return ret
    if retry:
        # at this point we have just an NVRA with no internal match. Open it up to externals
        query.clauses = orig_clauses
        ret = query.executeOne()
    if not ret:
        if strict:
            raise koji.GenericError("No such rpm: %r" % data)
        return None
    return ret


def list_rpms(buildID=None, buildrootID=None, imageID=None, componentBuildrootID=None, hostID=None,
              arches=None, queryOpts=None):
    """List RPMS.  If buildID, imageID and/or buildrootID are specified,
    restrict the list of RPMs to only those RPMs that are part of that
    build, or were built in that buildroot.  If componentBuildrootID is specified,
    restrict the list to only those RPMs that will get pulled into that buildroot
    when it is used to build another package.  A list of maps is returned, each map
    containing the following keys:

    - id
    - name
    - version
    - release
    - nvr (synthesized for sorting purposes)
    - arch
    - epoch
    - payloadhash
    - size
    - buildtime
    - build_id
    - buildroot_id
    - external_repo_id
    - external_repo_name
    - metadata_only
    - extra

    If componentBuildrootID is specified, two additional keys will be included:
    - component_buildroot_id
    - is_update

    If no build has the given ID, or the build generated no RPMs,
    an empty list is returned."""
    fields = [('rpminfo.id', 'id'), ('rpminfo.name', 'name'), ('rpminfo.version', 'version'),
              ('rpminfo.release', 'release'),
              ("rpminfo.name || '-' || rpminfo.version || '-' || rpminfo.release", 'nvr'),
              ('rpminfo.arch', 'arch'),
              ('rpminfo.epoch', 'epoch'), ('rpminfo.payloadhash', 'payloadhash'),
              ('rpminfo.size', 'size'), ('rpminfo.buildtime', 'buildtime'),
              ('rpminfo.build_id', 'build_id'), ('rpminfo.buildroot_id', 'buildroot_id'),
              ('rpminfo.external_repo_id', 'external_repo_id'),
              ('external_repo.name', 'external_repo_name'),
              ('rpminfo.metadata_only', 'metadata_only'),
              ('rpminfo.extra', 'extra'),
              ]
    joins = ['LEFT JOIN external_repo ON rpminfo.external_repo_id = external_repo.id']
    clauses = []

    if buildID is not None:
        clauses.append('rpminfo.build_id = %(buildID)i')
    if buildrootID is not None:
        clauses.append('rpminfo.buildroot_id = %(buildrootID)i')
    if componentBuildrootID is not None:
        fields.append(('buildroot_listing.buildroot_id as component_buildroot_id',
                       'component_buildroot_id'))
        fields.append(('buildroot_listing.is_update', 'is_update'))
        joins.append('buildroot_listing ON rpminfo.id = buildroot_listing.rpm_id')
        clauses.append('buildroot_listing.buildroot_id = %(componentBuildrootID)i')

    # image specific constraints
    if imageID is not None:
        clauses.append('archive_rpm_components.archive_id = %(imageID)i')
        joins.append('archive_rpm_components ON rpminfo.id = archive_rpm_components.rpm_id')

    if hostID is not None:
        joins.append(
            'standard_buildroot ON rpminfo.buildroot_id = standard_buildroot.buildroot_id')
        clauses.append('standard_buildroot.host_id = %(hostID)i')
    if arches is not None:
        if isinstance(arches, (list, tuple)):
            clauses.append('rpminfo.arch IN %(arches)s')
        elif isinstance(arches, str):
            clauses.append('rpminfo.arch = %(arches)s')
        else:
            raise koji.GenericError('invalid type for "arches" parameter: %s' % type(arches))

    fields, aliases = zip(*fields)
    query = QueryProcessor(columns=fields, aliases=aliases,
                           tables=['rpminfo'], joins=joins, clauses=clauses,
                           values=locals(), transform=_fix_rpm_row, opts=queryOpts)
    data = query.execute()
    return data


def get_maven_build(buildInfo, strict=False):
    """
    Retrieve Maven-specific information about a build.
    buildInfo can be either a string (n-v-r) or an integer
    (build ID).
    Returns a map containing the following keys:

    build_id: id of the build (integer)
    group_id: Maven groupId (string)
    artifact_id: Maven artifact_Id (string)
    version: Maven version (string)
    """
    fields = ('build_id', 'group_id', 'artifact_id', 'version')

    build_id = find_build_id(buildInfo, strict=strict)
    if not build_id:
        return None
    query = """SELECT %s
    FROM maven_builds
    WHERE build_id = %%(build_id)i""" % ', '.join(fields)
    return _singleRow(query, locals(), fields, strict)


def get_win_build(buildInfo, strict=False):
    """
    Retrieve Windows-specific information about a build.
    buildInfo can be either a string (n-v-r) or an integer
    (build ID).
    Returns a map containing the following keys:

    build_id: id of the build (integer)
    platform: the platform the build was performed on (string)
    """
    fields = ('build_id', 'platform')

    build_id = find_build_id(buildInfo, strict=strict)
    if not build_id:
        return None
    query = QueryProcessor(tables=('win_builds',), columns=fields,
                           clauses=('build_id = %(build_id)i',),
                           values={'build_id': build_id})
    result = query.executeOne()
    if strict and not result:
        raise koji.GenericError('no such Windows build: %s' % buildInfo)
    return result


def get_image_build(buildInfo, strict=False):
    """
    Retrieve image-specific information about a build.
    buildInfo can be either a string (n-v-r) or an integer
    (build ID). This function really only exists to verify a build
    is an image build; there is no additional data.

    Returns a map containing the following keys:
    build_id: id of the build
    """
    build_id = find_build_id(buildInfo, strict=strict)
    if not build_id:
        return None
    query = QueryProcessor(tables=('image_builds',), columns=('build_id',),
                           clauses=('build_id = %(build_id)i',),
                           values={'build_id': build_id})
    result = query.executeOne()
    if strict and not result:
        raise koji.GenericError('no such image build: %s' % buildInfo)
    return result


def get_build_type(buildInfo, strict=False):
    """Return type info about the build

    buildInfo should be a valid build specification

    Returns a dictionary whose keys are type names and whose values are
    the type info corresponding to that type
    """

    binfo = get_build(buildInfo, strict=strict)
    if not binfo:
        return None

    query = QueryProcessor(
        tables=['btype'],
        columns=['name'],
        joins=['build_types ON btype_id=btype.id'],
        clauses=['build_id = %(id)i'],
        values=binfo,
        opts={'asList': True},
    )

    ret = {}
    extra = binfo['extra'] or {}
    for (btype,) in query.execute():
        ret[btype] = extra.get('typeinfo', {}).get(btype)

    # deal with legacy types
    l_funcs = [['maven', get_maven_build], ['win', get_win_build],
               ['image', get_image_build]]
    for ltype, func in l_funcs:
        # For now, we let the legacy data take precedence, but at some point
        # we will want to change that
        ltinfo = func(binfo['id'], strict=False)
        if ltinfo:
            ret[ltype] = ltinfo

    return ret


def list_btypes(query=None, queryOpts=None):
    """List btypes matching query

    :param dict query: Select a particular btype by "name" or "id".
                       Example: {"name": "image"}.
                       If this parameter is None (default), Koji returns all
                       btypes.
    :param dict queryOpts: additional options for this query.
    :returns: a list of btype dicts. If you specify a query parameter for a
              btype name or id that does not exist, Koji will return an empty
              list.
    """
    if query is None:
        query = {}
    qparams = {'tables': ['btype'],
               'columns': ['id', 'name'],
               'opts': queryOpts}
    clauses = []
    values = query.copy()
    if 'name' in query:
        clauses.append('btype.name = %(name)s')
    if 'id' in query:
        clauses.append('btype.id = %(id)s')
    qparams['clauses'] = clauses
    qparams['values'] = values
    return QueryProcessor(**qparams).execute()


def add_btype(name):
    """Add a new btype with the given name"""
    context.session.assertPerm('admin')
    data = {'name': name}
    if list_btypes(data):
        raise koji.GenericError("btype already exists")
    insert = InsertProcessor('btype', data=data)
    insert.execute()


def list_archives(buildID=None, buildrootID=None, componentBuildrootID=None, hostID=None,
                  type=None, filename=None, size=None, checksum=None, typeInfo=None,
                  queryOpts=None, imageID=None, archiveID=None, strict=False):
    """
    Retrieve information about archives.
    If buildID is not null it will restrict the list to archives built by the build with that ID.
    If buildrootID is not null it will restrict the list to archives built in the buildroot with
    that ID.
    If componentBuildrootID is not null it will restrict the list to archives that were present in
    the buildroot with that ID.
    If hostID is not null it will restrict the list to archives built on the host with that ID.
    If filename, size, and/or checksum are not null it will filter the results to entries matching
    the provided values.

    Returns a list of maps containing the following keys:

    id: unique id of the archive file (integer)
    type_id: id of the archive type (Java jar, Solaris pkg, Windows exe, etc.) (integer)
    type_name: name of the archive type
    type_description: description of the archive
    type_extensions: valid extensions for the type
    build_id: id of the build that generated this archive (integer)
    buildroot_id: id of the buildroot where this archive was built (integer)
    filename: name of the archive (string)
    size: size of the archive (integer)
    checksum: checksum of the archive (string)
    checksum_type: the checksum type (integer)

    If componentBuildrootID is specified, then the map will also contain the following key:
    project: whether the archive was pulled in as a project dependency, or as part of the
             build environment setup (boolean)

    If 'type' is specified, then the archives listed will be limited
    those associated with additional metadata of the given type.
    Currently supported types are:

    maven, win, image

    If 'maven' is specified as a type, each returned map will contain
    these additional keys:

    group_id: Maven groupId (string)
    artifact_id: Maven artifactId (string)
    version: Maven version (string)

    if 'win' is specified as a type, each returned map will contain
    these additional keys:

    relpath: the relative path where the file is located (string)
    platforms: space-separated list of platforms the file is suitable for use on (string)
    flags: space-separated list of flags used when building the file (fre, chk) (string)

    if 'image' is specified as a type, each returned map will contain an
    additional key:

    arch: The architecture if the image itself, which may be different from the
          task that generated it

    typeInfo is a dict that can be used to filter the output by type-specific info.
    For the 'maven' type, this dict may contain one or more of group_id, artifact_id, or version,
      and the output will be restricted to archives with matching attributes.

    If there are no archives matching the selection criteria, if strict is False,
    an empty list is returned, otherwise GenericError is raised.
    """
    values = {}

    tables = ['archiveinfo']
    joins = ['archivetypes on archiveinfo.type_id = archivetypes.id',
             'btype ON archiveinfo.btype_id = btype.id']
    fields = [('archiveinfo.id', 'id'),
              ('archiveinfo.type_id', 'type_id'),
              ('archiveinfo.btype_id', 'btype_id'),
              ('btype.name', 'btype'),
              ('archiveinfo.build_id', 'build_id'),
              ('archiveinfo.buildroot_id', 'buildroot_id'),
              ('archiveinfo.filename', 'filename'),
              ('archiveinfo.size', 'size'),
              ('archiveinfo.checksum', 'checksum'),
              ('archiveinfo.checksum_type', 'checksum_type'),
              ('archiveinfo.metadata_only', 'metadata_only'),
              ('archiveinfo.extra', 'extra'),
              ('archivetypes.name', 'type_name'),
              ('archivetypes.description', 'type_description'),
              ('archivetypes.extensions', 'type_extensions'),
              ]
    clauses = []

    if buildID is not None:
        clauses.append('build_id = %(build_id)i')
        values['build_id'] = buildID
    if buildrootID is not None:
        clauses.append('buildroot_id = %(buildroot_id)i')
        values['buildroot_id'] = buildrootID
    if componentBuildrootID is not None:
        joins.append('buildroot_archives on archiveinfo.id = buildroot_archives.archive_id')
        clauses.append('buildroot_archives.buildroot_id = %(component_buildroot_id)i')
        values['component_buildroot_id'] = componentBuildrootID
        fields.append(['buildroot_archives.buildroot_id', 'component_buildroot_id'])
        fields.append(['buildroot_archives.project_dep', 'project'])
    if imageID is not None:
        # TODO: arg name is now a misnomer, could be any archive
        clauses.append('archive_components.archive_id = %(imageID)i')
        values['imageID'] = imageID
        joins.append('archive_components ON archiveinfo.id = archive_components.component_id')
    if hostID is not None:
        joins.append(
            'standard_buildroot on archiveinfo.buildroot_id = standard_buildroot.buildroot_id')
        clauses.append('standard_buildroot.host_id = %(host_id)i')
        values['host_id'] = hostID
        fields.append(['standard_buildroot.host_id', 'host_id'])
    if filename is not None:
        clauses.append('filename = %(filename)s')
        values['filename'] = filename
    if size is not None:
        clauses.append('size = %(size)i')
        values['size'] = size
    if checksum is not None:
        clauses.append('checksum = %(checksum)s')
        values['checksum'] = checksum
    if archiveID is not None:
        clauses.append('archiveinfo.id = %(archive_id)s')
        values['archive_id'] = archiveID

    if type is None:
        pass
    elif type == 'maven':
        joins.append('maven_archives ON archiveinfo.id = maven_archives.archive_id')
        fields.extend([
            ('maven_archives.group_id', 'group_id'),
            ('maven_archives.artifact_id', 'artifact_id'),
            ('maven_archives.version', 'version'),
        ])

        if typeInfo:
            for key in ('group_id', 'artifact_id', 'version'):
                if key in typeInfo:
                    clauses.append('maven_archives.%s = %%(%s)s' % (key, key))
                    values[key] = typeInfo[key]
    elif type == 'win':
        joins.append('win_archives ON archiveinfo.id = win_archives.archive_id')
        fields.extend([
            ('win_archives.relpath', 'relpath'),
            ('win_archives.platforms', 'platforms'),
            ('win_archives.flags', 'flags'),
        ])

        if typeInfo:
            if 'relpath' in typeInfo:
                clauses.append('win_archives.relpath = %(relpath)s')
                values['relpath'] = typeInfo['relpath']
            for key in ('platforms', 'flags'):
                if key in typeInfo:
                    val = typeInfo[key]
                    if not isinstance(val, (list, tuple)):
                        val = [val]
                    for i, v in enumerate(val):
                        pkey = '%s_pattern_%i' % (key, i)
                        values[pkey] = r'\m%s\M' % v
                        clauses.append('%s ~ %%(%s)s' % (key, pkey))
    elif type == 'image':
        joins.append('image_archives ON archiveinfo.id = image_archives.archive_id')
        fields.append(['image_archives.arch', 'arch'])
        if typeInfo and typeInfo.get('arch'):
            key = 'arch'
            clauses.append('image_archives.%s = %%(%s)s' % (key, key))
            values[key] = typeInfo[key]
    else:
        btype = lookup_name('btype', type, strict=False)
        if not btype:
            raise koji.GenericError('unsupported archive type: %s' % type)
        if typeInfo:
            raise koji.GenericError('typeInfo queries not supported for type '
                                    '%(name)s' % btype)
        clauses.append('archiveinfo.btype_id = %(btype_id)s')
        values['btype_id'] = btype['id']

    columns, aliases = zip(*fields)
    ret = QueryProcessor(tables=tables, columns=columns, aliases=aliases, joins=joins,
                         transform=_fix_archive_row,
                         clauses=clauses, values=values, opts=queryOpts).execute()
    if strict and not ret:
        raise koji.GenericError('No archives found.')
    return ret


def get_archive(archive_id, strict=False):
    """
    Get information about the archive with the given ID.  Returns a map
    containing the following keys:

    id: unique id of the archive file (integer)
    type_id: id of the archive type (Java jar, Solaris pkg, Windows exe, etc.) (integer)
    build_id: id of the build that generated this archive (integer)
    buildroot_id: id of the buildroot where this archive was built (integer)
    filename: name of the archive (string)
    size: size of the archive (integer)
    checksum: checksum of the archive (string)
    checksum_type: type of the checksum (integer)

    If the archive is part of a Maven build, the following keys will be included:
      group_id
      artifact_id
      version
    If the archive is part of a Windows builds, the following keys will be included:
      relpath
      platforms
      flags

    If the archive is part of an image build, and it is the image file that
    contains the root partitioning ('/'), there will be a additional fields:
      rootid
      arch
    """
    data = list_archives(archiveID=archive_id)
    if not data:
        if strict:
            raise koji.GenericError('No such archive: %s' % archive_id)
        else:
            return None

    archive = data[0]
    maven_info = get_maven_archive(archive_id)
    if maven_info:
        del maven_info['archive_id']
        archive.update(maven_info)
    win_info = get_win_archive(archive_id)
    if win_info:
        del win_info['archive_id']
        archive.update(win_info)
    image_info = get_image_archive(archive_id)
    if image_info:
        del image_info['archive_id']
        archive.update(image_info)
    return archive


def get_maven_archive(archive_id, strict=False):
    """
    Retrieve Maven-specific information about an archive.
    Returns a map containing the following keys:

    archive_id: id of the build (integer)
    group_id: Maven groupId (string)
    artifact_id: Maven artifact_Id (string)
    version: Maven version (string)
    """
    fields = ('archive_id', 'group_id', 'artifact_id', 'version')
    select = """SELECT %s FROM maven_archives
    WHERE archive_id = %%(archive_id)i""" % ', '.join(fields)
    return _singleRow(select, locals(), fields, strict=strict)


def get_win_archive(archive_id, strict=False):
    """
    Retrieve Windows-specific information about an archive.
    Returns a map containing the following keys:

    archive_id: id of the build (integer)
    relpath: the relative path where the file is located (string)
    platforms: space-separated list of platforms the file is suitable for use on (string)
    flags: space-separated list of flags used when building the file (fre, chk) (string)
    """
    fields = ('archive_id', 'relpath', 'platforms', 'flags')
    select = """SELECT %s FROM win_archives
    WHERE archive_id = %%(archive_id)i""" % ', '.join(fields)
    return _singleRow(select, locals(), fields, strict=strict)


def get_image_archive(archive_id, strict=False):
    """
    Retrieve image-specific information about an archive.
    Returns a map containing the following keys:

    archive_id: id of the build (integer)
    arch: the architecture of the image
    rootid: True if this image has the root '/' partition
    """
    fields = ('archive_id', 'arch')
    select = """SELECT %s FROM image_archives
    WHERE archive_id = %%(archive_id)i""" % ', '.join(fields)
    results = _singleRow(select, locals(), fields, strict=strict)
    if not results:
        return None
    results['rootid'] = False
    fields = ['rpm_id']
    select = """SELECT %s FROM archive_rpm_components
    WHERE archive_id = %%(archive_id)i""" % ', '.join(fields)
    rpms = _singleRow(select, locals(), fields)
    if rpms:
        results['rootid'] = True
    return results


def _get_zipfile_list(archive_id, zippath):
    """
    Get a list of the entries in the zipfile located at zippath.
    Return a list of dicts, one per entry in the zipfile.  Each dict contains:
     - archive_id
     - name
     - size
    If the file does not exist, return an empty list.
    """
    result = []
    if not os.path.exists(zippath):
        return result
    with zipfile.ZipFile(zippath, 'r') as archive:
        for entry in archive.infolist():
            filename = koji.fixEncoding(entry.filename)
            result.append({'archive_id': archive_id,
                           'name': filename,
                           'size': entry.file_size,
                           'mtime': int(time.mktime(entry.date_time + (0, 0, -1)))})
    return result


def _get_tarball_list(archive_id, tarpath):
    """
    Get a list of the entries in the tarball located at tarpath.
    Return a list of dicts, one per entry in the tarball.  Each dict contains:
     - archive_id
     - name
     - size
     - mtime
     - mode
     - user
     - group
    If the file does not exist, return an empty list.
    """
    result = []
    if not os.path.exists(tarpath):
        return result
    with tarfile.open(tarpath, 'r') as archive:
        for entry in archive:
            filename = koji.fixEncoding(entry.name)
            result.append({'archive_id': archive_id,
                           'name': filename,
                           'size': entry.size,
                           'mtime': entry.mtime,
                           'mode': entry.mode,
                           'user': entry.uname,
                           'group': entry.gname})
    return result


def list_archive_files(archive_id, queryOpts=None, strict=False):
    """
    Get information about the files contained in the archive with the given ID.
    Returns a list of maps with with following keys:

    archive_id: id of the archive the file is contained in (integer)
    name: name of the file (string)
    size: uncompressed size of the file (integer)

    If strict is True, raise GenericError if archive_type is not one that we
    are able to expand

    Regardless of strict, an error will be raised if the archive_id is invalid
    """
    archive_info = get_archive(archive_id, strict=True)

    archive_type = get_archive_type(type_id=archive_info['type_id'], strict=True)
    build_info = get_build(archive_info['build_id'], strict=True)
    btype = archive_info['btype']

    if btype == 'maven':
        maven_archive = get_maven_archive(archive_info['id'], strict=True)
        archive_info.update(maven_archive)
        file_path = joinpath(koji.pathinfo.mavenbuild(build_info),
                             koji.pathinfo.mavenfile(archive_info))
    elif btype == 'win':
        win_archive = get_win_archive(archive_info['id'], strict=True)
        archive_info.update(win_archive)
        file_path = joinpath(koji.pathinfo.winbuild(build_info),
                             koji.pathinfo.winfile(archive_info))
    elif btype == 'image':
        image_archive = get_image_archive(archive_info['id'], strict=True)
        archive_info.update(image_archive)
        file_path = joinpath(koji.pathinfo.imagebuild(build_info),
                             archive_info['filename'])
    elif btype:
        # for non-legacy types, btype info is in the 'extra' field
        file_path = joinpath(koji.pathinfo.typedir(build_info, btype),
                             archive_info['filename'])
    else:
        # should not happen
        raise koji.GenericError("Missing build type info for archive %s" % archive_id)

    if archive_type['name'] in ('zip', 'jar'):
        filelist = _get_zipfile_list(archive_id, file_path)
    elif archive_type['name'] == 'tar':
        filelist = _get_tarball_list(archive_id, file_path)
    else:
        # TODO: support other archive types
        if strict:
            raise koji.GenericError(
                "Unsupported archive type: %s" % archive_type['name'])
        filelist = []
    return _applyQueryOpts(filelist, queryOpts)


def get_archive_file(archive_id, filename, strict=False):
    """
    Get information about a file with the given filename
    contained in the archive with the given ID.
    Returns a map with with following keys:

    archive_id: id of the archive the file is contained in (integer)
    name: name of the file (string)
    size: uncompressed size of the file (integer)

    If strict is True, raise GenericError if:
      - this file is not found in the archive
      - build btype of this archive belong to is not maven, win or image
      - archive_type is not that we are able to expand

    Regardless of strict, an error will be raised if the archive_id is invalid
    """
    files = list_archive_files(archive_id, strict=strict)
    for file_info in files:
        if file_info['name'] == filename:
            return file_info
    if strict:
        raise koji.GenericError('No such file: %s in archive#%s' % (filename, archive_id))
    return None


def list_task_output(taskID, stat=False, all_volumes=False, strict=False):
    """List the files generated by the task with the given ID.  This
    will usually include one or more RPMs, and one or more log files.
    If the task did not generate any files, or the output directory
    for the task no longer exists, return an empty list.

    If stat is True, return a map of filename -> stat_info where stat_info
    is a map containing the values of the st_* attributes returned by
    os.stat().

    If all_volumes is set, results are extended to deal with files in same
    relative paths on different volumes.

    With all_volumes=True, stat=False, return a map of filename -> list_of_volumes,
        {'stdout.log': ['DEFAULT']}

    With all_volumes=True, stat=True, return a map of
    filename -> map_of_volumes -> stat_info,
        {'stdout.log':
            {'DEFAULT': {
                {
                    'st_atime': 1488902587.2141163,
                    'st_ctime': 1488902588.2281106,
                    'st_mtime': 1488902588.2281106,
                    'st_size': '526'
                }
            }
        }

    If strict is set, function will raise a GenericError if task doesn't
    exist. Allows user to distinguish between empty output and non-existent task.
    """
    if strict:
        # raise error if task doesn't exist
        try:
            Task(taskID).getInfo(strict=True)
        except Exception:
            raise koji.GenericError("Task doesn't exist")

    if stat or all_volumes:
        result = {}
    else:
        result = []

    if all_volumes:
        volumes = [x['name'] for x in list_volumes()]
    else:
        volumes = ['DEFAULT']

    for volume in volumes:
        taskDir = '%s/%s' % (koji.pathinfo.work(volume=volume), koji.pathinfo.taskrelpath(taskID))
        if not os.path.isdir(taskDir):
            continue
        for path, dirs, files in os.walk(taskDir):
            for filename in files:
                relpath = path[len(taskDir) + 1:]
                relfilename = joinpath(relpath, filename)
                if stat:
                    stat_info = os.stat(joinpath(path, filename))
                    stat_map = {}
                    for attr in dir(stat_info):
                        if attr == 'st_size':
                            stat_map[attr] = str(getattr(stat_info, attr))
                        elif attr in ('st_atime', 'st_mtime', 'st_ctime'):
                            stat_map[attr] = getattr(stat_info, attr)
                    if all_volumes:
                        result.setdefault(relfilename, {})[volume] = stat_map
                    else:
                        result[relfilename] = stat_map
                else:
                    if all_volumes:
                        result.setdefault(relfilename, []).append(volume)
                    else:
                        result.append(relfilename)
    return result


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


def _dml(operation, values):
    """Run an insert, update, or delete. Return number of rows affected"""
    c = context.cnx.cursor()
    c.execute(operation, values)
    ret = c.rowcount
    logger.debug("Operation affected %s row(s)", ret)
    c.close()
    context.commit_pending = True
    return ret


def get_host(hostInfo, strict=False, event=None):
    """Get information about the given host.  hostInfo may be
    either a string (hostname) or int (host id).  A map will be returned
    containing the following data:

    - id
    - user_id
    - name
    - arches
    - task_load
    - capacity
    - description
    - comment
    - ready
    - enabled
    """
    tables = ['host_config']
    joins = ['host ON host.id = host_config.host_id']

    fields = {'host.id': 'id',
              'host.user_id': 'user_id',
              'host.name': 'name',
              'host.ready': 'ready',
              'host.task_load': 'task_load',
              'host_config.arches': 'arches',
              'host_config.capacity': 'capacity',
              'host_config.description': 'description',
              'host_config.comment': 'comment',
              'host_config.enabled': 'enabled',
              }
    clauses = [eventCondition(event, table='host_config')]

    if isinstance(hostInfo, int):
        clauses.append("host.id = %(hostInfo)i")
    elif isinstance(hostInfo, str):
        clauses.append("host.name = %(hostInfo)s")
    else:
        raise koji.GenericError('invalid type for hostInfo: %s' % type(hostInfo))

    data = {'hostInfo': hostInfo}
    fields, aliases = zip(*fields.items())
    query = QueryProcessor(columns=fields, aliases=aliases, tables=tables,
                           joins=joins, clauses=clauses, values=data)
    result = query.executeOne()
    if not result:
        if strict:
            raise koji.GenericError('Invalid hostInfo: %s' % hostInfo)
        return None
    return result


def edit_host(hostInfo, **kw):
    """Edit information for an existing host.
    hostInfo specifies the host to edit, either as an integer (id)
    or a string (name).
    fields to be changed are specified as keyword parameters:
    - arches (a space-separated string)
    - capacity (float or int)
    - description (string)
    - comment (string)

    Returns True if changes are made to the database, False otherwise.
    """
    context.session.assertPerm('host')

    host = get_host(hostInfo, strict=True)

    fields = ('arches', 'capacity', 'description', 'comment')
    changes = []
    for field in fields:
        if field in kw and kw[field] != host[field]:
            changes.append(field)

    if not changes:
        return False

    update = UpdateProcessor('host_config', values=host, clauses=['host_id = %(id)i'])
    update.make_revoke()
    update.execute()

    insert = InsertProcessor('host_config',
                             data=dslice(host,
                                         ('arches', 'capacity', 'description', 'comment',
                                          'enabled')))
    insert.set(host_id=host['id'])
    for change in changes:
        insert.set(**{change: kw[change]})
    insert.make_create()
    insert.execute()

    return True


def get_channel(channelInfo, strict=False):
    """
    Look up the ID number and name for a channel.

    :param channelInfo: channel ID or name
    :type channelInfo: int or str
    :param bool strict: If True, raise an error if we found no matching
                        channel. If False, simply return None if we found no
                        matching channel. If unspecified, the default value is
                        False.
    :returns: dict of the channel ID and name, or None.
              For example, {'id': 20, 'name': 'container'}
    """
    fields = ('id', 'name')
    query = """SELECT %s FROM channels
    WHERE """ % ', '.join(fields)
    if isinstance(channelInfo, int):
        query += """id = %(channelInfo)i"""
    elif isinstance(channelInfo, str):
        query += """name = %(channelInfo)s"""
    else:
        raise koji.GenericError('invalid type for channelInfo: %s' % type(channelInfo))

    return _singleRow(query, locals(), fields, strict)


def query_buildroots(hostID=None, tagID=None, state=None, rpmID=None, archiveID=None, taskID=None,
                     buildrootID=None, queryOpts=None):
    """Return a list of matching buildroots

    Optional args:
        hostID - only buildroots on host.
        tagID - only buildroots for tag.
        state - only buildroots in state (may be a list)
        rpmID - only buildroots the specified rpm was used in
        archiveID - only buildroots the specified archive was used in
        taskID - only buildroots associated with task.
        buildrootID - only the specified buildroot
        queryOpts - query options
    """
    fields = [('buildroot.id', 'id'),
              ('buildroot.br_type', 'br_type'),
              ('buildroot.cg_id', 'cg_id'),
              ('content_generator.name', 'cg_name'),
              ('buildroot.cg_version', 'cg_version'),
              ('buildroot.container_arch', 'container_arch'),
              ('buildroot.container_arch', 'arch'),  # alias for back compat
              ('buildroot.container_type', 'container_type'),
              ('buildroot.host_os', 'host_os'),
              ('buildroot.host_arch', 'host_arch'),
              ('buildroot.extra', 'extra'),
              ('standard_buildroot.state', 'state'),
              ('standard_buildroot.task_id', 'task_id'),
              ('host.id', 'host_id'), ('host.name', 'host_name'),
              ('repo.id', 'repo_id'), ('repo.state', 'repo_state'),
              ('tag.id', 'tag_id'), ('tag.name', 'tag_name'),
              ('create_events.id', 'create_event_id'), ('create_events.time', 'create_event_time'),
              ('EXTRACT(EPOCH FROM create_events.time)', 'create_ts'),
              ('retire_events.id', 'retire_event_id'), ('retire_events.time', 'retire_event_time'),
              ('EXTRACT(EPOCH FROM retire_events.time)', 'retire_ts'),
              ('repo_create.id', 'repo_create_event_id'),
              ('repo_create.time', 'repo_create_event_time')]

    tables = ['buildroot']
    joins = ['LEFT OUTER JOIN standard_buildroot '
             'ON standard_buildroot.buildroot_id = buildroot.id',
             'LEFT OUTER JOIN content_generator '
             'ON buildroot.cg_id = content_generator.id',
             'LEFT OUTER JOIN host ON host.id = standard_buildroot.host_id',
             'LEFT OUTER JOIN repo ON repo.id = standard_buildroot.repo_id',
             'LEFT OUTER JOIN tag ON tag.id = repo.tag_id',
             'LEFT OUTER JOIN events AS create_events ON '
             'create_events.id = standard_buildroot.create_event',
             'LEFT OUTER JOIN events AS retire_events ON '
             'standard_buildroot.retire_event = retire_events.id',
             'LEFT OUTER JOIN events AS repo_create ON repo_create.id = repo.create_event']

    clauses = []
    if buildrootID is not None:
        if isinstance(buildrootID, (list, tuple)):
            clauses.append('buildroot.id IN %(buildrootID)s')
        else:
            clauses.append('buildroot.id = %(buildrootID)i')
    if hostID is not None:
        clauses.append('host.id = %(hostID)i')
    if tagID is not None:
        clauses.append('tag.id = %(tagID)i')
    if state is not None:
        if isinstance(state, (list, tuple)):
            clauses.append('standard_buildroot.state IN %(state)s')
        else:
            clauses.append('standard_buildroot.state = %(state)i')

    # following filters can dramatically limit overall query size
    # run separate queries for picking smallest candidate set
    candidate_buildroot_ids = set()
    if rpmID is not None:
        query = QueryProcessor(columns=['buildroot_id'], tables=['buildroot_listing'],
                               clauses=['rpm_id = %(rpmID)i'], opts={'asList': True},
                               values=locals())
        result = set(query.execute())
        candidate_buildroot_ids = result
        if not candidate_buildroot_ids:
            return _applyQueryOpts([], queryOpts)

    if archiveID is not None:
        query = QueryProcessor(columns=['buildroot_id'], tables=['buildroot_archives'],
                               clauses=['archive_id = %(archiveID)i'], opts={'asList': True},
                               values=locals())
        result = set(query.execute())
        if candidate_buildroot_ids:
            candidate_buildroot_ids &= result
        else:
            candidate_buildroot_ids = result
        if not candidate_buildroot_ids:
            return _applyQueryOpts([], queryOpts)

    if taskID is not None:
        query = QueryProcessor(columns=['buildroot_id'], tables=['standard_buildroot'],
                               clauses=['task_id = %(taskID)i'], opts={'asList': True},
                               values=locals())
        result = set(query.execute())
        if candidate_buildroot_ids:
            candidate_buildroot_ids &= result
        else:
            candidate_buildroot_ids = result
        if not candidate_buildroot_ids:
            return _applyQueryOpts([], queryOpts)

    if candidate_buildroot_ids:
        candidate_buildroot_ids = list(candidate_buildroot_ids)
        clauses.append('buildroot.id IN %(candidate_buildroot_ids)s')

    query = QueryProcessor(columns=[f[0] for f in fields], aliases=[f[1] for f in fields],
                           tables=tables, joins=joins, clauses=clauses, values=locals(),
                           transform=_fix_extra_field,
                           opts=queryOpts)
    return query.execute()


def get_buildroot(buildrootID, strict=False):
    """Return information about a buildroot.  buildrootID must be an int ID."""

    result = query_buildroots(buildrootID=buildrootID)
    if len(result) == 0:
        if strict:
            raise koji.GenericError("No such buildroot: %r" % buildrootID)
        else:
            return None
    if len(result) > 1:
        # this should be impossible
        raise koji.GenericError("More that one buildroot with id: %i" % buildrootID)
    return result[0]


def list_channels(hostID=None, event=None):
    """
    List builder channels.

    :param hostID: Koji builder host ID or hostname. If specified, Koji will
                   return only the channels associated with this builder host.
                   If unspecified, Koji will return all channels.
    :type hostID: int or str
    :param int event: The event ID at which to search. If unspecified, the
                      default behavior is to search for the "active" host
                      settings. You must specify a hostID parameter with this
                      option.
    :returns: list of dicts, one per channel. For example,
              [{'id': 20, 'name': 'container'}]
    """
    fields = {'channels.id': 'id', 'channels.name': 'name'}
    columns, aliases = zip(*fields.items())
    if hostID:
        tables = ['host_channels']
        joins = ['channels ON channels.id = host_channels.channel_id']
        clauses = [
            eventCondition(event, table='host_channels'),
            'host_channels.host_id = %(host_id)s']
        values = {'host_id': hostID}
        query = QueryProcessor(tables=tables, aliases=aliases,
                               columns=columns, joins=joins,
                               clauses=clauses, values=values)
    elif event:
        raise koji.GenericError('list_channels with event and '
                                'not host is not allowed.')
    else:
        query = QueryProcessor(tables=['channels'], aliases=aliases,
                               columns=columns)
    return query.execute()


def new_package(name, strict=True):
    c = context.cnx.cursor()
    # TODO - table lock?
    # check for existing
    q = """SELECT id FROM package WHERE name=%(name)s"""
    c.execute(q, locals())
    row = c.fetchone()
    if row:
        (pkg_id,) = row
        if strict:
            raise koji.GenericError("Package already exists [id %d]" % pkg_id)
    else:
        q = """SELECT nextval('package_id_seq')"""
        c.execute(q)
        (pkg_id,) = c.fetchone()
        q = """INSERT INTO package (id,name) VALUES (%(pkg_id)s,%(name)s)"""
        context.commit_pending = True
        c.execute(q, locals())
    return pkg_id


def add_volume(name, strict=True):
    """Add a new storage volume in the database"""
    context.session.assertPerm('admin')
    voldir = koji.pathinfo.volumedir(name)
    if not os.path.isdir(voldir):
        raise koji.GenericError('please create the volume directory first')
    if strict:
        volinfo = lookup_name('volume', name, strict=False)
        if volinfo:
            raise koji.GenericError('volume %s already exists' % name)
    volinfo = lookup_name('volume', name, strict=False, create=True)
    return volinfo


def remove_volume(volume):
    """Remove unused storage volume from the database"""
    context.session.assertPerm('admin')
    volinfo = lookup_name('volume', volume, strict=True)
    query = QueryProcessor(tables=['build'], clauses=['volume_id=%(id)i'],
                           values=volinfo, columns=['id'], opts={'limit': 1})
    if query.execute():
        raise koji.GenericError('volume %(name)s has build references' % volinfo)
    delete = """DELETE FROM volume WHERE id=%(id)i"""
    _dml(delete, volinfo)


def list_volumes():
    """List storage volumes"""
    return QueryProcessor(tables=['volume'], columns=['id', 'name']).execute()


def change_build_volume(build, volume, strict=True):
    """Move a build to a different storage volume"""
    context.session.assertPerm('admin')
    volinfo = lookup_name('volume', volume, strict=True)
    binfo = get_build(build, strict=True)
    _set_build_volume(binfo, volinfo, strict)


def _set_build_volume(binfo, volinfo, strict=True):
    """Move a build to a different storage volume"""
    if binfo['volume_id'] == volinfo['id']:
        if strict:
            raise koji.GenericError("Build %(nvr)s already on volume %(volume_name)s" % binfo)
        else:
            # nothing to do
            return
    state = koji.BUILD_STATES[binfo['state']]
    if state not in ['COMPLETE', 'DELETED']:
        raise koji.GenericError("Build %s is %s" % (binfo['nvr'], state))
    voldir = koji.pathinfo.volumedir(volinfo['name'])
    if not os.path.isdir(voldir):
        raise koji.GenericError("Directory entry missing for volume %(name)s" % volinfo)

    # more sanity checks
    for check_vol in list_volumes():
        check_binfo = binfo.copy()
        check_binfo['volume_id'] = check_vol['id']
        check_binfo['volume_name'] = check_vol['name']
        checkdir = koji.pathinfo.build(check_binfo)
        if check_vol['id'] == binfo['volume_id']:
            # the volume we are moving from
            pass
        elif check_vol['name'] == 'DEFAULT' and os.path.islink(checkdir):
            # old convenience symlink
            pass
        elif check_vol['id'] == volinfo['id']:
            # the volume we are moving to
            if os.path.lexists(checkdir):
                raise koji.GenericError("Destination directory exists: %s" % checkdir)
        elif os.path.lexists(checkdir):
            raise koji.GenericError("Unexpected cross-volume content: %s" % checkdir)

    # First copy the build dir(s)
    dir_moves = []
    old_binfo = binfo.copy()
    binfo['volume_id'] = volinfo['id']
    binfo['volume_name'] = volinfo['name']
    olddir = koji.pathinfo.build(old_binfo)
    if os.path.exists(olddir):
        newdir = koji.pathinfo.build(binfo)
        dir_moves.append([olddir, newdir])
    for olddir, newdir in dir_moves:
        # Remove old symlink if copying to base volume
        if volinfo['name'] == 'DEFAULT' or volinfo['name'] is None:
            if os.path.islink(newdir):
                os.unlink(newdir)
        koji.ensuredir(os.path.dirname(newdir))
        shutil.copytree(olddir, newdir, symlinks=True)

    # Second, update the db
    koji.plugin.run_callbacks('preBuildStateChange', attribute='volume_id',
                              old=old_binfo['volume_id'], new=volinfo['id'], info=binfo)
    update = UpdateProcessor('build', clauses=['id=%(id)i'], values=binfo)
    update.set(volume_id=volinfo['id'])
    update.execute()
    for tag in list_tags(build=binfo['id']):
        set_tag_update(tag['id'], 'VOLUME_CHANGE')

    # Third, delete the old content
    for olddir, newdir in dir_moves:
        koji.util.rmtree(olddir)

    # Fourth, maintain a symlink if appropriate
    if volinfo['name'] and volinfo['name'] != 'DEFAULT':
        base_vol = lookup_name('volume', 'DEFAULT', strict=True)
        base_binfo = binfo.copy()
        base_binfo['volume_id'] = base_vol['id']
        base_binfo['volume_name'] = base_vol['name']
        basedir = koji.pathinfo.build(base_binfo)
        if os.path.islink(basedir):
            os.unlink(basedir)
        relpath = os.path.relpath(newdir, os.path.dirname(basedir))
        os.symlink(relpath, basedir)

    koji.plugin.run_callbacks('postBuildStateChange', attribute='volume_id',
                              old=old_binfo['volume_id'], new=volinfo['id'], info=binfo)


def ensure_volume_symlink(binfo):
    """Ensure that a build has a symlink on the default volume if needed"""

    # basic checks
    volname = binfo.get('volume_name')
    if volname is None:
        logger.warning('buildinfo has no volume data, cannot create symlink')
        return
    if volname == 'DEFAULT':
        # nothing to do
        return

    # get the actual build dir
    build_dir = koji.pathinfo.build(binfo)

    # get the default volume location for the symlink
    base_vol = lookup_name('volume', 'DEFAULT', strict=True)
    base_binfo = binfo.copy()
    base_binfo['volume_id'] = base_vol['id']
    base_binfo['volume_name'] = base_vol['name']
    basedir = koji.pathinfo.build(base_binfo)

    # check/make the symlink
    relpath = os.path.relpath(build_dir, os.path.dirname(basedir))
    if os.path.islink(basedir):
        if os.readlink(basedir) == relpath:
            # already correct
            return
        os.unlink(basedir)
    elif os.path.exists(basedir):
        raise koji.GenericError('Unexpected build content: %s' % basedir)
    else:
        # parent dir might not exist
        koji.ensuredir(os.path.dirname(basedir))
    os.symlink(relpath, basedir)


def check_volume_policy(data, strict=False, default=None):
    """Check volume policy for the given data

    If strict is True, raises exception when a volume cannot be determined.
    The default option can either be None, or a valid volume id or name, and
    is used when the policy rules do not return a match.

    Returns volume info or None
    """
    result = None
    try:
        ruleset = context.policy.get('volume')
        result = ruleset.apply(data)
    except Exception:
        logger.error('Volume policy error')
        if strict:
            raise
        tb_str = ''.join(traceback.format_exception(*sys.exc_info()))
        logger.debug(tb_str)
    logger.debug('Volume policy returned %s', result)
    if result is not None:
        vol = lookup_name('volume', result)
        if vol:
            return vol
        # otherwise
        if strict:
            raise koji.GenericError("Policy returned invalid volume: %s"
                                    % result)
        logger.error('Volume policy returned unknown volume %s', result)
    # fall back to default
    if default is not None:
        vol = lookup_name('volume', default)
        if vol:
            return vol
        if strict:
            raise koji.GenericError("Invalid default volume: %s" % default)
        logger.error('Invalid default volume: %s', default)
    if strict:
        raise koji.GenericError('No volume policy match')
    logger.warning('No volume policy match')
    return None


def apply_volume_policy(build, strict=False):
    """Apply volume policy, moving build as needed

    build should be the buildinfo returned by get_build()

    The strict options determines what happens in the case of a bad policy.
    If strict is True, an exception will be raised. Otherwise, the existing
    volume we be retained.
    """
    policy_data = {'build': build}
    task_id = build['task_id']
    if task_id:
        policy_data.update(policy_data_from_task(task_id))
    volume = check_volume_policy(policy_data, strict=strict)
    if volume is None:
        # just leave the build where it is
        return
    if build['volume_id'] == volume['id']:
        # nothing to do
        return
    _set_build_volume(build, volume, strict=True)


def new_build(data, strict=False):
    """insert a new build entry

    If strict is specified, raise an exception, if build already exists.
    """

    data = data.copy()

    # basic sanity checks
    if 'pkg_id' in data:
        data['name'] = lookup_package(data['pkg_id'], strict=True)['name']
    else:
        # see if there's a package name
        name = data.get('name')
        if not name:
            raise koji.GenericError("No name or package id provided for build")
        data['pkg_id'] = new_package(name, strict=False)
    if data.get('owner'):
        # check, that user exists (and convert name to id)
        data['owner'] = get_user(data['owner'], strict=True)['id']
    for f in ('version', 'release', 'epoch'):
        if f not in data:
            raise koji.GenericError("No %s value for build" % f)
    if 'extra' in data:
        try:
            data['extra'] = json.dumps(data['extra'])
        except Exception:
            raise koji.GenericError("Invalid build extra data: %(extra)r" % data)
    else:
        data['extra'] = None

    # provide a few default values
    data.setdefault('state', koji.BUILD_STATES['COMPLETE'])
    data.setdefault('start_time', 'NOW')
    data.setdefault('completion_time', 'NOW')
    data.setdefault('source', None)
    data.setdefault('owner', context.session.user_id)
    data.setdefault('task_id', None)
    data.setdefault('volume_id', 0)

    # check for existing build
    old_binfo = get_build(data)
    if old_binfo:
        if strict:
            raise koji.GenericError('Existing build found: %s' % data)
        recycle_build(old_binfo, data)
        # Raises exception if there is a problem
        return old_binfo['id']
    koji.plugin.run_callbacks('preBuildStateChange', attribute='state', old=None,
                              new=data['state'], info=data)

    # insert the new data
    insert_data = dslice(data, ['pkg_id', 'version', 'release', 'epoch', 'state', 'volume_id',
                                'task_id', 'owner', 'start_time', 'completion_time', 'source',
                                'extra'])
    if 'cg_id' in data:
        insert_data['cg_id'] = data['cg_id']
    data['id'] = insert_data['id'] = _singleValue("SELECT nextval('build_id_seq')")
    insert = InsertProcessor('build', data=insert_data)
    insert.execute()
    new_binfo = get_build(data['id'], strict=True)
    koji.plugin.run_callbacks('postBuildStateChange', attribute='state', old=None,
                              new=data['state'], info=new_binfo)
    # return build_id
    return data['id']


def recycle_build(old, data):
    """Check to see if a build can by recycled and if so, update it"""

    st_desc = koji.BUILD_STATES[old['state']]
    if st_desc == 'BUILDING':
        # check to see if this is the controlling task
        if data['state'] == old['state'] and data.get('task_id', '') == old['task_id']:
            # the controlling task must have restarted (and called initBuild again)
            return
        raise koji.GenericError("Build already in progress (task %(task_id)d)"
                                % old)
        # TODO? - reclaim 'stale' builds (state=BUILDING and task_id inactive)

    if st_desc not in ('FAILED', 'CANCELED'):
        raise koji.GenericError("Build already exists (id=%d, state=%s): %r"
                                % (old['id'], st_desc, data))

    # check for evidence of tag activity
    query = QueryProcessor(columns=['tag_id'], tables=['tag_listing'],
                           clauses=['build_id = %(id)s'], values=old)
    if query.execute():
        raise koji.GenericError("Build already exists. Unable to recycle, "
                                "has tag history")

    # check for rpms or archives
    query = QueryProcessor(columns=['id'], tables=['rpminfo'],
                           clauses=['build_id = %(id)s'], values=old)
    if query.execute():
        raise koji.GenericError("Build already exists. Unable to recycle, "
                                "has rpm data")
    query = QueryProcessor(columns=['id'], tables=['archiveinfo'],
                           clauses=['build_id = %(id)s'], values=old)
    if query.execute():
        raise koji.GenericError("Build already exists. Unable to recycle, "
                                "has archive data")

    # If we reach here, should be ok to replace

    koji.plugin.run_callbacks('preBuildStateChange', attribute='state',
                              old=old['state'], new=data['state'], info=data)

    # If there is any old build type info, clear it
    delete = """DELETE FROM maven_builds WHERE build_id = %(id)i"""
    _dml(delete, old)
    delete = """DELETE FROM win_builds WHERE build_id = %(id)i"""
    _dml(delete, old)
    delete = """DELETE FROM image_builds WHERE build_id = %(id)i"""
    _dml(delete, old)
    delete = """DELETE FROM build_types WHERE build_id = %(id)i"""
    _dml(delete, old)

    data['id'] = old['id']
    update = UpdateProcessor('build', clauses=['id=%(id)s'], values=data)
    update.set(**dslice(data,
                        ['state', 'task_id', 'owner', 'start_time', 'completion_time',
                         'epoch', 'source', 'extra', 'volume_id']))
    if 'cg_id' in data:
        update.set(cg_id=data['cg_id'])
    update.rawset(create_event='get_event()')
    update.execute()
    builddir = koji.pathinfo.build(data)
    if os.path.exists(builddir):
        koji.util.rmtree(builddir)
    buildinfo = get_build(data['id'], strict=True)
    koji.plugin.run_callbacks('postBuildStateChange', attribute='state',
                              old=old['state'], new=data['state'], info=buildinfo)


def check_noarch_rpms(basepath, rpms, logs=None):
    """
    If rpms contains any noarch rpms with identical names,
    run rpmdiff against the duplicate rpms.
    Return the list of rpms with any duplicate entries removed (only
    the first entry will be retained).
    """
    result = []
    noarch_rpms = {}
    if logs is None:
        logs = {}
    for relpath in rpms:
        if relpath.endswith('.noarch.rpm'):
            filename = os.path.basename(relpath)
            if filename in noarch_rpms:
                # duplicate found, add it to the duplicate list
                # but not the result list
                noarch_rpms[filename].append(relpath)
            else:
                noarch_rpms[filename] = [relpath]
                result.append(relpath)
        else:
            result.append(relpath)

    hashes = {}
    for arch in logs:
        for log in logs[arch]:
            if os.path.basename(log) == 'noarch_rpmdiff.json':
                task_hash = json.load(open(joinpath(basepath, log), 'rt'))
                for task_id in task_hash:
                    hashes[task_id] = task_hash[task_id]

    for noarch_list in noarch_rpms.values():
        if len(noarch_list) < 2:
            continue
        rpmdiff(basepath, noarch_list, hashes=hashes)

    return result


def import_build(srpm, rpms, brmap=None, task_id=None, build_id=None, logs=None):
    """Import a build into the database (single transaction)

    Files must be uploaded and specified with path relative to the workdir
    Args:
        srpm - relative path of srpm
        rpms - list of rpms (relative paths)
        brmap - dictionary mapping [s]rpms to buildroot ids
        task_id - associate the build with a task
        build_id - build is a finalization of existing entry
    """
    if brmap is None:
        brmap = {}
    koji.plugin.run_callbacks('preImport', type='build', srpm=srpm, rpms=rpms, brmap=brmap,
                              task_id=task_id, build_id=build_id, build=None, logs=logs)
    uploadpath = koji.pathinfo.work()
    # verify files exist
    for relpath in [srpm] + rpms:
        fn = "%s/%s" % (uploadpath, relpath)
        if not os.path.exists(fn):
            raise koji.GenericError("no such file: %s" % fn)

    rpms = check_noarch_rpms(uploadpath, rpms, logs=logs)

    # verify buildroot ids from brmap
    found = {}
    for br_id in brmap.values():
        if br_id in found:
            continue
        found[br_id] = 1
        # this will raise an exception if the buildroot id is invalid
        BuildRoot(br_id)

    # get build informaton
    fn = "%s/%s" % (uploadpath, srpm)
    build = koji.get_header_fields(fn, ('name', 'version', 'release', 'epoch',
                                        'sourcepackage'))
    if build['sourcepackage'] != 1:
        raise koji.GenericError("not a source package: %s" % fn)
    build['task_id'] = task_id

    policy_data = {
        'package': build['name'],
        'version': build['version'],
        'release': build['release'],
        'buildroots': to_list(brmap.values()),
        'import': True,
        'import_type': 'rpm',
    }
    if task_id is not None:
        policy_data.update(policy_data_from_task(task_id))
    vol = check_volume_policy(policy_data, strict=False, default='DEFAULT')
    build['volume_id'] = vol['id']
    build['volume_name'] = vol['name']

    if build_id is None:
        build_id = new_build(build)
        binfo = get_build(build_id, strict=True)
        new_typed_build(binfo, 'rpm')
    else:
        # build_id was passed in - sanity check
        binfo = get_build(build_id, strict=True)
        st_complete = koji.BUILD_STATES['COMPLETE']
        st_old = binfo['state']
        koji.plugin.run_callbacks('preBuildStateChange', attribute='state', old=st_old,
                                  new=st_complete, info=binfo)
        for key in ('name', 'version', 'release', 'epoch', 'task_id'):
            if build[key] != binfo[key]:
                raise koji.GenericError(
                    "Unable to complete build: %s mismatch (build: %s, rpm: %s)" %
                    (key, binfo[key], build[key]))
        if binfo['state'] != koji.BUILD_STATES['BUILDING']:
            raise koji.GenericError("Unable to complete build: state is %s"
                                    % koji.BUILD_STATES[binfo['state']])
        # update build state
        update = UpdateProcessor('build', clauses=['id=%(id)s'], values=binfo)
        update.set(state=st_complete)
        update.rawset(completion_time='NOW()')
        update.set(volume_id=build['volume_id'])
        update.execute()
        binfo = get_build(build_id, strict=True)
        koji.plugin.run_callbacks('postBuildStateChange', attribute='state', old=st_old,
                                  new=st_complete, info=binfo)

    # now to handle the individual rpms
    for relpath in [srpm] + rpms:
        fn = "%s/%s" % (uploadpath, relpath)
        rpminfo = import_rpm(fn, binfo, brmap.get(relpath))
        import_rpm_file(fn, binfo, rpminfo)
        add_rpm_sig(rpminfo['id'], koji.rip_rpm_sighdr(fn))
    if logs:
        for key, files in logs.items():
            if not key:
                key = None
            for relpath in files:
                fn = "%s/%s" % (uploadpath, relpath)
                import_build_log(fn, binfo, subdir=key)

    ensure_volume_symlink(binfo)

    koji.plugin.run_callbacks('postImport', type='build', srpm=srpm, rpms=rpms, brmap=brmap,
                              task_id=task_id, build_id=build_id, build=binfo, logs=logs)
    return binfo


def import_rpm(fn, buildinfo=None, brootid=None, wrapper=False, fileinfo=None):
    """Import a single rpm into the database

    Designed to be called from import_build.
    """
    if not os.path.exists(fn):
        raise koji.GenericError("no such file: %s" % fn)

    # read rpm info
    hdr = koji.get_rpm_header(fn)
    rpminfo = koji.get_header_fields(hdr, ['name', 'version', 'release', 'epoch',
                                           'sourcepackage', 'arch', 'buildtime', 'sourcerpm'])
    if rpminfo['sourcepackage'] == 1:
        rpminfo['arch'] = "src"

    # sanity check basename
    basename = os.path.basename(fn)
    expected = "%(name)s-%(version)s-%(release)s.%(arch)s.rpm" % rpminfo
    if basename != expected:
        raise koji.GenericError("bad filename: %s (expected %s)" % (basename, expected))

    if buildinfo is None:
        # figure it out for ourselves
        if rpminfo['sourcepackage'] == 1:
            buildinfo = get_build(rpminfo, strict=False)
            if not buildinfo:
                # create a new build
                build_id = new_build(rpminfo)
                # we add the rpm build type below
                buildinfo = get_build(build_id, strict=True)
        else:
            # figure it out from sourcerpm string
            buildinfo = get_build(koji.parse_NVRA(rpminfo['sourcerpm']))
            if buildinfo is None:
                # XXX - handle case where package is not a source rpm
                #      and we still need to create a new build
                raise koji.GenericError('No matching build')
            state = koji.BUILD_STATES[buildinfo['state']]
            if state in ('FAILED', 'CANCELED', 'DELETED'):
                nvr = "%(name)s-%(version)s-%(release)s" % buildinfo
                raise koji.GenericError("Build is %s: %s" % (state, nvr))
    elif not wrapper:
        # only enforce the srpm name matching the build for non-wrapper rpms
        srpmname = "%(name)s-%(version)s-%(release)s.src.rpm" % buildinfo
        # either the sourcerpm field should match the build, or the filename
        # itself (for the srpm)
        if rpminfo['sourcepackage'] != 1:
            if rpminfo['sourcerpm'] != srpmname:
                raise koji.GenericError("srpm mismatch for %s: %s (expected %s)"
                                        % (fn, rpminfo['sourcerpm'], srpmname))
        elif basename != srpmname:
            raise koji.GenericError("srpm mismatch for %s: %s (expected %s)"
                                    % (fn, basename, srpmname))

    # if we're adding an rpm to it, then this build is of rpm type
    # harmless if build already has this type
    new_typed_build(buildinfo, 'rpm')

    # add rpminfo entry
    rpminfo['id'] = _singleValue("""SELECT nextval('rpminfo_id_seq')""")
    rpminfo['build_id'] = buildinfo['id']
    rpminfo['size'] = os.path.getsize(fn)
    rpminfo['payloadhash'] = koji.hex_string(koji.get_header_field(hdr, 'sigmd5'))
    rpminfo['buildroot_id'] = brootid
    rpminfo['external_repo_id'] = 0

    # handle cg extra info
    if fileinfo is not None:
        extra = fileinfo.get('extra')
        if extra is not None:
            rpminfo['extra'] = json.dumps(extra)

    koji.plugin.run_callbacks('preImport', type='rpm', rpm=rpminfo, build=buildinfo,
                              filepath=fn, fileinfo=fileinfo)

    data = rpminfo.copy()
    del data['sourcepackage']
    del data['sourcerpm']
    insert = InsertProcessor('rpminfo', data=data)
    insert.execute()

    koji.plugin.run_callbacks('postImport', type='rpm', rpm=rpminfo, build=buildinfo,
                              filepath=fn, fileinfo=fileinfo)

    # extra fields for return
    rpminfo['build'] = buildinfo
    rpminfo['brootid'] = brootid
    return rpminfo


def generate_token(nbytes=32):
    """
    Generate random hex-string token of length 2 * nbytes
    """
    if secrets:
        return secrets.token_hex(nbytes=nbytes)
    else:
        values = ['%02x' % random.randint(0, 255) for x in range(nbytes)]
        return ''.join(values)


def get_reservation_token(build_id):
    query = QueryProcessor(
        tables=['build_reservations'],
        columns=['build_id', 'token'],
        clauses=['build_id = %(build_id)d'],
        values=locals(),
    )
    return query.executeOne()


def clear_reservation(build_id):
    '''Remove reservation entry for build'''
    delete = "DELETE FROM build_reservations WHERE build_id = %(build_id)i"
    _dml(delete, {'build_id': build_id})


def cg_init_build(cg, data):
    """Create (reserve) a build_id for given data.

    If build or reservation already exists, init_build will raise GenericError

    :param str cg: content generator name
    :param dict data: build data same as for new_build, for given usecase
                      only name,version,release,epoch keys make sense. Some
                      other values will be ignored anyway (owner, state, ...)
    :return: dict with build_id and token
    """
    assert_cg(cg)
    cg_id = lookup_name('content_generator', cg, strict=True)['id']
    data['owner'] = context.session.user_id
    data['state'] = koji.BUILD_STATES['BUILDING']
    data['completion_time'] = None
    data['cg_id'] = cg_id
    # CGs shouldn't have to worry about epoch
    data.setdefault('epoch', None)
    build_id = new_build(data, strict=False)

    # check potentially existing token
    if get_reservation_token(build_id):
        raise koji.GenericError("Build is already reserved")

    # store token
    token = generate_token()
    insert = InsertProcessor(table='build_reservations')
    insert.set(build_id=build_id, token=token)
    insert.rawset(created='NOW()')
    insert.execute()

    return {'build_id': build_id, 'token': token}


def cg_refund_build(cg, build_id, token, state=koji.BUILD_STATES['FAILED']):
    """If build is reserved and not finished yet, there is an option
    to release reservation and mark build either FAILED or CANCELED.
    For this calling CG needs to know build_id and reservation token.

    Refunded build behaves like any other failed/canceled build. So,
    its nvr can be reclaimed again and get_next_release can return
    this nvr.

    :param str cg: content generator name
    :param int build_id: build id
    :param str token: token from CGInitBuild
    :param int state: new state (koji.BUILD_STATES)

    :return: None, on error raises exception
    """

    if state not in (koji.BUILD_STATES['FAILED'], koji.BUILD_STATES['CANCELED']):
        raise koji.GenericError("Only FAILED/CANCELLED build states are allowed")

    assert_cg(cg)
    binfo = get_build(build_id, strict=True)
    if binfo['state'] != koji.BUILD_STATES['BUILDING']:
        raise koji.GenericError('Build ID %s is not in BUILDING state' % build_id)

    build_token = get_reservation_token(build_id)
    if not build_token or build_token['token'] != token:
        raise koji.GenericError("Token doesn't match build ID %s" % build_id)

    cg_id = lookup_name('content_generator', cg, strict=True)['id']
    if binfo['cg_id'] != cg_id:
        raise koji.GenericError('Build ID %s is not reserved by this CG' % build_id)

    koji.plugin.run_callbacks('preBuildStateChange', attribute='state',
                              old=koji.BUILD_STATES['BUILDING'], new=state, info=binfo)

    update = UpdateProcessor('build', values={'id': build_id}, clauses=["id = %(id)s"])
    update.set(state=state)
    update.rawset(completion_time='NOW()')
    update.execute()

    binfo = get_build(build_id, strict=True)
    koji.plugin.run_callbacks('postBuildStateChange', attribute='state',
                              old=koji.BUILD_STATES['BUILDING'], new=state, info=binfo)
    clear_reservation(build_id)


def cg_import(metadata, directory, token=None):
    """Import build from a content generator

    metadata can be one of the following
    - json encoded string representing the metadata
    - a dictionary (parsed metadata)
    - a filename containing the metadata

    :param metadata: describes the content for this build.
    :param str directory: directory on the hub where files are located
    :param str token: (optional) a reservation token for this build.
                      You obtain a token from the CGInitBuild method.
                      If you specify a token, you must also specify a build_id
                      in the metadata.
    :returns: buildinfo dict
    """

    importer = CG_Importer()
    return importer.do_import(metadata, directory, token)


class CG_Importer(object):

    def __init__(self):
        self.buildinfo = None
        self.metadata_only = False

    def do_import(self, metadata, directory, token=None):
        metadata = self.get_metadata(metadata, directory)
        self.directory = directory

        metaver = metadata['metadata_version']
        if metaver != 0:
            raise koji.GenericError("Unknown metadata version: %r" % metaver)

        # TODO: basic metadata sanity check (use jsonschema?)

        self.assert_cg_access()

        # prepare data for import
        self.prep_build(token)
        self.prep_brs()
        self.prep_outputs()

        self.assert_policy()
        self.set_volume()
        self.check_build_dir()

        koji.plugin.run_callbacks('preImport', type='cg', metadata=metadata,
                                  directory=directory)

        # finalize import
        self.get_build(token)
        self.import_brs()
        try:
            self.import_outputs()
            self.import_metadata()
        except Exception:
            self.check_build_dir(delete=True)
            raise

        koji.plugin.run_callbacks('postImport', type='cg', metadata=metadata,
                                  directory=directory, build=self.buildinfo)

        return self.buildinfo

    def get_metadata(self, metadata, directory):
        """Get the metadata from the args"""

        if isinstance(metadata, dict):
            self.metadata = metadata
            try:
                self.raw_metadata = json.dumps(metadata, indent=2)
            except Exception:
                logger.exception("Cannot encode supplied metadata")
                raise koji.GenericError("Invalid metadata, cannot encode: %r" % metadata)
            return metadata
        if metadata is None:
            # default to looking for uploaded file
            metadata = 'metadata.json'
        if not isinstance(metadata, str):
            raise koji.GenericError("Invalid metadata value: %r" % metadata)
        if metadata.endswith('.json'):
            # handle uploaded metadata
            workdir = koji.pathinfo.work()
            path = joinpath(workdir, directory, metadata)
            if not os.path.exists(path):
                raise koji.GenericError("No such file: %s" % metadata)
            with open(path, 'rt') as fo:
                metadata = fo.read()
        self.raw_metadata = metadata
        self.metadata = parse_json(metadata, desc='metadata')
        return self.metadata

    def assert_cg_access(self):
        """Check that user has access for all referenced content generators"""

        cgs = set()
        for brdata in self.metadata['buildroots']:
            cginfo = brdata['content_generator']
            cg = lookup_name('content_generator', cginfo['name'], strict=True)
            cgs.add(cg['id'])
            brdata['cg_id'] = cg['id']
        for cg_id in cgs:
            assert_cg(cg_id)
        self.cgs = cgs

    def assert_policy(self):
        policy_data = {
            'package': self.buildinfo['name'],
            'source': self.buildinfo.get('source'),
            'metadata_only': self.metadata_only,
            'cg_list': list(self.cgs),
            # TODO: provide more data
        }
        assert_policy('cg_import', policy_data)

    def set_volume(self):
        """Use policy to determine what the volume should be"""
        # we have to be careful and provide sufficient data
        policy_data = {
            'package': self.buildinfo['name'],
            'version': self.buildinfo['version'],
            'release': self.buildinfo['release'],
            'source': self.buildinfo['source'],
            'cg_list': list(self.cgs),
            'import': True,
            'import_type': 'cg',
        }
        vol = check_volume_policy(policy_data, strict=False)
        if vol:
            self.buildinfo['volume_id'] = vol['id']
            self.buildinfo['volume_name'] = vol['name']

    def check_build_dir(self, delete=False):
        """Check that the import directory does not already exist"""
        path = koji.pathinfo.build(self.buildinfo)
        if os.path.lexists(path):
            if delete:
                logger.warning("Deleting build directory: %s", path)
                koji.util.rmtree(path)
            else:
                raise koji.GenericError("Destination directory already exists: %s" % path)

    def prep_build(self, token=None):
        metadata = self.metadata
        if metadata['build'].get('build_id'):
            if len(self.cgs) != 1:
                raise koji.GenericError(
                    "Reserved builds can handle only single content generator.")
            cg_id = list(self.cgs)[0]
            build_id = metadata['build']['build_id']
            buildinfo = get_build(build_id, strict=True)
            build_token = get_reservation_token(build_id)
            if not build_token or build_token['token'] != token:
                raise koji.GenericError("Token doesn't match build ID %s" % build_id)
            if buildinfo['cg_id'] != cg_id:
                raise koji.GenericError('Build ID %s is not reserved by this CG' % build_id)
            if buildinfo.get('task_id'):
                raise koji.GenericError('Build is owned by task %(task_id)s' % buildinfo)
            if buildinfo['state'] != koji.BUILD_STATES['BUILDING']:
                raise koji.GenericError('Build ID %s is not in BUILDING state' % build_id)
            if buildinfo['name'] != metadata['build']['name'] or \
               buildinfo['version'] != metadata['build']['version'] or \
               buildinfo['release'] != metadata['build']['release']:
                raise koji.GenericError("Build (%i) NVR is different" % build_id)
            if ('epoch' in metadata['build'] and
                    buildinfo['epoch'] != metadata['build']['epoch']):
                raise koji.GenericError("Build (%i) epoch is different"
                                        % build_id)

        elif token is not None:
            raise koji.GenericError('Reservation token given, but no build_id '
                                    'in metadata')
        else:
            buildinfo = get_build(metadata['build'], strict=False)
            if buildinfo and not metadata['build'].get('build_id'):
                # TODO : allow in some cases
                raise koji.GenericError("Build already exists: %r" % buildinfo)
        # gather needed data
        buildinfo = dslice(metadata['build'], ['name', 'version', 'release', 'extra', 'source'])
        if 'build_id' in metadata['build']:
            buildinfo['build_id'] = metadata['build']['build_id']
        # epoch is not in the metadata spec, but we allow it to be specified
        buildinfo['epoch'] = metadata['build'].get('epoch', None)
        buildinfo['start_time'] = \
            datetime.datetime.fromtimestamp(float(metadata['build']['start_time'])).isoformat(' ')
        buildinfo['completion_time'] = \
            datetime.datetime.fromtimestamp(float(metadata['build']['end_time'])).isoformat(' ')
        owner = metadata['build'].get('owner', None)
        if owner:
            if not isinstance(owner, str):
                raise koji.GenericError("Invalid owner format (expected username): %s" % owner)
            buildinfo['owner'] = get_user(owner, strict=True)['id']
        self.buildinfo = buildinfo

        koji.check_NVR(buildinfo, strict=True)

        # get typeinfo
        buildinfo.setdefault('extra', {})
        b_extra = buildinfo['extra']
        b_extra.setdefault('typeinfo', {})
        typeinfo = b_extra['typeinfo']

        # legacy types can be at top level of extra
        for btype in ['maven', 'win', 'image']:
            if btype not in b_extra:
                continue
            if btype in typeinfo:
                # he says they've already got one
                raise koji.GenericError('Duplicate typeinfo for %r' % btype)
            typeinfo[btype] = b_extra[btype]

        # sanity check
        for btype in typeinfo:
            lookup_name('btype', btype, strict=True)

        self.typeinfo = typeinfo
        return buildinfo

    def get_build(self, token=None):
        if token:
            # token and reservation were already checked in prep_build
            buildinfo = self.update_build()
            build_id = buildinfo['build_id']
        else:
            # no reservation, we need create a new build entry
            build_id = new_build(self.buildinfo)
            buildinfo = get_build(build_id, strict=True)

        # handle special build types
        for btype in self.typeinfo:
            tinfo = self.typeinfo[btype]
            if btype == 'maven':
                new_maven_build(buildinfo, tinfo)
            elif btype == 'win':
                new_win_build(buildinfo, tinfo)
            elif btype == 'image':
                # no extra info tracked at build level
                new_image_build(buildinfo)
            else:
                new_typed_build(buildinfo, btype)

        # rpm builds not required to have typeinfo
        if 'rpm' not in self.typeinfo:
            # if the build contains rpms then it has the rpm type
            if [o for o in self.prepped_outputs if o['type'] == 'rpm']:
                new_typed_build(buildinfo, 'rpm')

        self.buildinfo = buildinfo
        return buildinfo

    def update_build(self):
        """Update a reserved build"""
        # sanity checks performed by prep_build
        build_id = self.buildinfo['build_id']
        old_info = get_build(build_id, strict=True)
        if self.buildinfo.get('extra'):
            extra = json.dumps(self.buildinfo['extra'])
        else:
            extra = None
        owner = self.buildinfo.get('owner', context.session.user_id)
        source = self.buildinfo.get('source')
        st_complete = koji.BUILD_STATES['COMPLETE']
        st_old = old_info['state']
        koji.plugin.run_callbacks('preBuildStateChange', attribute='state', old=st_old,
                                  new=st_complete, info=old_info)
        update = UpdateProcessor('build', clauses=['id=%(build_id)s'], values=self.buildinfo)
        update.set(state=st_complete, extra=extra, owner=owner, source=source)
        if self.buildinfo.get('volume_id'):
            # reserved builds have reapplied volume policy now
            update.set(volume_id=self.buildinfo['volume_id'])
        update.rawset(completion_time='NOW()')
        update.execute()
        buildinfo = get_build(build_id, strict=True)
        clear_reservation(build_id)
        koji.plugin.run_callbacks('postBuildStateChange', attribute='state', old=st_old,
                                  new=st_complete, info=buildinfo)

        return buildinfo

    def import_metadata(self):
        """Import the raw metadata"""

        # TODO - eventually, import this as an archive, but for now we just write it to disk
        #   because there are complications
        #       - no buildroot (could confuse policies checking that builds were built sanely
        #       - doesn't fit with current major archive categories
        builddir = koji.pathinfo.build(self.buildinfo)
        koji.ensuredir(builddir)
        path = joinpath(builddir, 'metadata.json')
        with open(path, 'w') as fo:
            fo.write(self.raw_metadata)

    def prep_brs(self):
        metadata = self.metadata
        br_used = set([f['buildroot_id'] for f in metadata['output']])
        br_idx = {}
        for brdata in metadata['buildroots']:
            brfakeid = brdata['id']
            if brfakeid not in br_used:
                raise koji.GenericError("Buildroot id not used in output: %r" % brfakeid)
            if brfakeid in br_idx:
                raise koji.GenericError("Duplicate buildroot id in metadata: %r" % brfakeid)
            br_idx[brfakeid] = self.prep_buildroot(brdata)
        self.br_prep = br_idx

    def import_brs(self):
        brmap = {}
        for brfakeid in self.br_prep:
            entry = self.br_prep[brfakeid]
            brmap[brfakeid] = self.import_buildroot(entry)
        self.brmap = brmap

    def prep_buildroot(self, brdata):
        ret = {}
        brinfo = {
            'cg_id': brdata['cg_id'],
            'cg_version': brdata['content_generator']['version'],
            'container_type': brdata['container']['type'],
            'container_arch': brdata['container']['arch'],
            'host_os': brdata['host']['os'],
            'host_arch': brdata['host']['arch'],
            'extra': brdata.get('extra'),
        }
        rpmlist, archives = self.match_components(brdata['components'])
        ret = {
            'brinfo': brinfo,
            'rpmlist': rpmlist,
            'archives': archives,
            'tools': brdata['tools'],
        }
        return ret

    def import_buildroot(self, entry):
        """Import the prepared buildroot data"""

        # buildroot entry
        br = BuildRoot()
        br.cg_new(entry['brinfo'])

        # buildroot components
        br.setList(entry['rpmlist'])
        br.updateArchiveList(entry['archives'])

        # buildroot_tools_info
        br.setTools(entry['tools'])

        return br

    def match_components(self, components):
        rpms = []
        files = []
        for comp in components:
            if comp['type'] == 'rpm':
                match = self.match_rpm(comp)
                if match:
                    rpms.append(match)
            elif comp['type'] == 'file':
                match = self.match_file(comp)
                if match:
                    files.append(match)
            elif comp['type'] == 'kojifile':
                match = self.match_kojifile(comp)
                if match:
                    files.append(match)
            else:
                raise koji.GenericError("Unknown component type: %(type)s" % comp)
        return rpms, files

    def match_rpm(self, comp):
        # TODO: do we allow inclusion of external rpms?
        if 'location' in comp:
            raise koji.GenericError("External rpms not allowed")
        if 'id' in comp:
            # not in metadata spec, and will confuse get_rpm
            raise koji.GenericError("Unexpected 'id' field in component")
        rinfo = get_rpm(comp, strict=False)
        if not rinfo:
            # XXX - this is a temporary workaround until we can better track external refs
            logger.warning("IGNORING unmatched rpm component: %r", comp)
            return None
        if rinfo['payloadhash'] != comp['sigmd5']:
            # XXX - this is a temporary workaround until we can better track external refs
            logger.warning("IGNORING rpm component (md5 mismatch): %r", comp)
            # nvr = "%(name)s-%(version)s-%(release)s" % rinfo
            # raise koji.GenericError("md5sum mismatch for %s: %s != %s"
            #            % (nvr, comp['sigmd5'], rinfo['payloadhash']))
        # TODO - should we check the signature field?
        return rinfo

    def match_file(self, comp):
        # hmm, how do we look up archives?
        # updateMavenBuildRootList does seriously wild stuff
        # only unique field in archiveinfo is id
        # checksum/checksum_type only works if type matches
        # at the moment, we only have md5 entries in archiveinfo

        type_mismatches = 0
        for archive in list_archives(filename=comp['filename'], size=comp['filesize']):
            if archive['checksum_type'] != koji.CHECKSUM_TYPES[comp['checksum_type']]:
                type_mismatches += 1
                continue
            if archive['checksum'] == comp['checksum']:
                return archive
        # else
        logger.error("Failed to match archive %(filename)s (size %(filesize)s, sum %(checksum)s",
                     comp)
        if type_mismatches:
            logger.error("Match failed with %i type mismatches", type_mismatches)
        # TODO: allow external archives
        # XXX - this is a temporary workaround until we can better track external refs
        logger.warning("IGNORING unmatched archive: %r", comp)
        return None
        # raise koji.GenericError("No match: %(filename)s (size %(filesize)s, sum %(checksum)s" %
        #                         comp)

    def match_kojifile(self, comp):
        """Look up the file by archive id and sanity check the other data"""
        assert(comp['type'] == 'kojifile')
        archive = get_archive(comp['archive_id'], strict=True)
        build = get_build(archive['build_id'], strict=True)

        for key in ['nvr', 'filename']:
            if key not in comp:
                raise koji.GenericError('%s field missing for component, '
                                        'archive_id=%s' % (key, archive['id']))
        expected = {
            'nvr': build['nvr'],
            'filename': archive['filename'],
            'filesize': int(archive['size']),
            'checksum': archive['checksum'],
            'checksum_type': koji.CHECKSUM_TYPES[archive['checksum_type']],
        }
        for key in expected:
            if key in comp and expected[key] != comp[key]:
                raise koji.GenericError('Component field %s does not match for '
                                        'archive_id=%s: %s != %s' % (key, archive['id'],
                                                                     expected[key], comp[key]))
        return archive

    def prep_outputs(self):
        metadata = self.metadata
        outputs = []
        for fileinfo in metadata['output']:
            fileinfo = fileinfo.copy()  # [!]
            if fileinfo.get('metadata_only', False):
                self.metadata_only = True
            workdir = koji.pathinfo.work()
            path = joinpath(workdir, self.directory, fileinfo.get('relpath', ''),
                            fileinfo['filename'])
            fileinfo['hub.path'] = path

            filesize = os.path.getsize(path)
            if filesize != fileinfo['filesize']:
                raise koji.GenericError(
                    "File size %s for %s (expected %s) doesn't match. Corrupted upload?" %
                    (filesize, fileinfo['filename'], fileinfo['filesize']))

            # checksum
            with open(path, 'rb') as fp:
                chksum = get_verify_class(fileinfo['checksum_type'])()
                while True:
                    contents = fp.read(8192)
                    if not contents:
                        break
                    chksum.update(contents)
                if fileinfo['checksum'] != chksum.hexdigest():
                    raise koji.GenericError("File checksum mismatch for %s: %s != %s" %
                                            (fileinfo['filename'], fileinfo['checksum'],
                                             chksum.hexdigest()))
            fileinfo['hub.checked_hash'] = True

            if fileinfo['buildroot_id'] not in self.br_prep:
                raise koji.GenericError("Missing buildroot metadata for id %(buildroot_id)r" %
                                        fileinfo)
            if fileinfo['type'] not in ['rpm', 'log']:
                self.prep_archive(fileinfo)
            if fileinfo['type'] == 'rpm':
                koji.check_NVRA(fileinfo['filename'], strict=True)
            outputs.append(fileinfo)
        self.prepped_outputs = outputs

    def import_outputs(self):
        for fileinfo in self.prepped_outputs:
            brinfo = self.brmap.get(fileinfo['buildroot_id'])
            if not brinfo:
                # should not happen
                logger.error("No buildroot mapping for file: %r", fileinfo)
                raise koji.GenericError("Unable to map buildroot %(buildroot_id)s" % fileinfo)
            if fileinfo['type'] == 'rpm':
                self.import_rpm(self.buildinfo, brinfo, fileinfo)
            elif fileinfo['type'] == 'log':
                self.import_log(self.buildinfo, fileinfo)
            else:
                self.import_archive(self.buildinfo, brinfo, fileinfo)
        ensure_volume_symlink(self.buildinfo)

    def prep_archive(self, fileinfo):
        # determine archive import type
        extra = fileinfo.get('extra', {})
        legacy_types = ['maven', 'win', 'image']
        btype = None
        type_info = None
        for key in extra:
            if key not in legacy_types:
                continue
            if btype is not None:
                raise koji.GenericError("Output file has multiple types: "
                                        "%(filename)s" % fileinfo)
            btype = key
            type_info = extra[key]
        for key in extra.get('typeinfo', {}):
            if btype == key:
                raise koji.GenericError("Duplicate typeinfo for: %r" % btype)
            elif btype is not None:
                raise koji.GenericError("Output file has multiple types: "
                                        "%(filename)s" % fileinfo)
            btype = key
            type_info = extra['typeinfo'][key]

        if btype is None:
            raise koji.GenericError("No typeinfo for: %(filename)s" % fileinfo)

        if btype not in self.typeinfo:
            raise koji.GenericError('Output type %s not listed in build '
                                    'types' % btype)

        fileinfo['hub.btype'] = btype
        fileinfo['hub.type_info'] = type_info

        if 'components' in fileinfo:
            if btype in ('maven', 'win'):
                raise koji.GenericError("Component list not allowed for "
                                        "archives of type %s" % btype)
            # for new types, we trust the metadata
            components = fileinfo['components']
            rpmlist, archives = self.match_components(components)
            # TODO - note presence of external components
            fileinfo['hub.rpmlist'] = rpmlist
            fileinfo['hub.archives'] = archives

    def import_rpm(self, buildinfo, brinfo, fileinfo):
        if fileinfo.get('metadata_only', False):
            raise koji.GenericError('Metadata-only imports are not supported for rpms')
            # TODO - support for rpms too
        fn = fileinfo['hub.path']
        rpminfo = import_rpm(fn, buildinfo, brinfo.id, fileinfo=fileinfo)
        import_rpm_file(fn, buildinfo, rpminfo)
        add_rpm_sig(rpminfo['id'], koji.rip_rpm_sighdr(fn))

    def import_log(self, buildinfo, fileinfo):
        if fileinfo.get('metadata_only', False):
            # logs are not currently tracked, so this is a no op
            return
        # TODO: determine subdir
        fn = fileinfo['hub.path']
        import_build_log(fn, buildinfo, subdir=None)

    def import_archive(self, buildinfo, brinfo, fileinfo):
        fn = fileinfo['hub.path']
        btype = fileinfo['hub.btype']
        type_info = fileinfo['hub.type_info']

        archiveinfo = import_archive_internal(fn, buildinfo, btype, type_info, brinfo.id, fileinfo)

        if 'components' in fileinfo:
            self.import_components(archiveinfo['id'], fileinfo)

    def import_components(self, archive_id, fileinfo):
        rpmlist = fileinfo['hub.rpmlist']
        archives = fileinfo['hub.archives']

        if rpmlist:
            insert = BulkInsertProcessor('archive_rpm_components')
            for rpminfo in rpmlist:
                insert.add_record(archive_id=archive_id, rpm_id=rpminfo['id'])
            insert.execute()

        if archives:
            insert = BulkInsertProcessor('archive_components')
            for archiveinfo in archives:
                insert.add_record(archive_id=archive_id, component_id=archiveinfo['id'])
            insert.execute()


def add_external_rpm(rpminfo, external_repo, strict=True):
    """Add an external rpm entry to the rpminfo table

    Differences from import_rpm:
        - entry will have non-zero external_repo_id
        - entry will not reference a build
        - rpm not available to us -- the necessary data is passed in

    The rpminfo arg should contain the following fields:
        - name, version, release, epoch, arch, payloadhash, size, buildtime

    Returns info as get_rpm
    """

    # [!] Calling function should perform access checks

    # sanity check rpminfo
    dtypes = (
        ('name', str),
        ('version', str),
        ('release', str),
        ('epoch', (int, type(None))),
        ('arch', str),
        ('payloadhash', str),
        ('size', int),
        ('buildtime', int))
    for field, allowed in dtypes:
        if field not in rpminfo:
            raise koji.GenericError("%s field missing: %r" % (field, rpminfo))
        if not isinstance(rpminfo[field], allowed):
            # this will catch unwanted NULLs
            raise koji.GenericError("Invalid value for %s: %r" % (field, rpminfo[field]))
    # strip extra fields
    rpminfo = dslice(rpminfo, [x[0] for x in dtypes])
    # TODO: more sanity checks for payloadhash

    def check_dup():
        # Check to see if we have it
        data = rpminfo.copy()
        data['location'] = external_repo
        previous = get_rpm(data, strict=False)
        if previous:
            disp = "%(name)s-%(version)s-%(release)s.%(arch)s@%(external_repo_name)s" % previous
            if strict:
                raise koji.GenericError("external rpm already exists: %s" % disp)
            elif data['payloadhash'] != previous['payloadhash']:
                raise koji.GenericError("hash changed for external rpm: %s (%s -> %s)"
                                        % (disp, previous['payloadhash'], data['payloadhash']))
            else:
                return previous

    previous = check_dup()
    if previous:
        return previous

    # add rpminfo entry
    data = rpminfo.copy()
    data['external_repo_id'] = get_external_repo_id(external_repo, strict=True)
    data['id'] = nextval('rpminfo_id_seq')
    data['build_id'] = None
    data['buildroot_id'] = None
    insert = InsertProcessor('rpminfo', data=data)
    savepoint = Savepoint('pre_insert')
    try:
        insert.execute()
    except Exception:
        # if this failed, it likely duplicates one just inserted
        # see: https://pagure.io/koji/issue/788
        savepoint.rollback()
        previous = check_dup()
        if previous:
            return previous
        raise

    return get_rpm(data['id'])


def import_build_log(fn, buildinfo, subdir=None):
    """Move a logfile related to a build to the right place"""
    logdir = koji.pathinfo.build_logs(buildinfo)
    if subdir:
        logdir = "%s/%s" % (logdir, subdir)
    koji.ensuredir(logdir)
    final_path = "%s/%s" % (logdir, os.path.basename(fn))
    if os.path.exists(final_path):
        raise koji.GenericError("Error importing build log. %s already exists." % final_path)
    if os.path.islink(fn) or not os.path.isfile(fn):
        raise koji.GenericError("Error importing build log. %s is not a regular file." % fn)
    move_and_symlink(fn, final_path)


def import_rpm_file(fn, buildinfo, rpminfo):
    """Move the rpm file into the proper place

    Generally this is done after the db import
    """
    final_path = "%s/%s" % (koji.pathinfo.build(buildinfo), koji.pathinfo.rpm(rpminfo))
    _import_archive_file(fn, os.path.dirname(final_path))


def _import_wrapper(task_id, build_info, rpm_results):
    """Helper function to import wrapper rpms for a Maven build"""
    rpm_buildroot_id = rpm_results['buildroot_id']
    rpm_task_dir = koji.pathinfo.task(task_id)

    for rpm_path in [rpm_results['srpm']] + rpm_results['rpms']:
        rpm_path = joinpath(rpm_task_dir, rpm_path)
        rpm_info = import_rpm(rpm_path, build_info, rpm_buildroot_id, wrapper=True)
        import_rpm_file(rpm_path, build_info, rpm_info)
        add_rpm_sig(rpm_info['id'], koji.rip_rpm_sighdr(rpm_path))

    for log in rpm_results['logs']:
        # assume we're only importing noarch packages
        import_build_log(joinpath(rpm_task_dir, log),
                         build_info, subdir='noarch')


def merge_scratch(task_id):
    """Import rpms from a scratch build into an existing build, retaining
    buildroot metadata and build logs."""
    task = Task(task_id)
    try:
        task_info = task.getInfo(request=True)
    except koji.GenericError:
        raise koji.ImportError('invalid task: %s' % task_id)
    task_params = koji.tasks.parse_task_params(task_info['method'], task_info['request'])
    if task_info['state'] != koji.TASK_STATES['CLOSED']:
        raise koji.ImportError('task %s did not complete successfully' % task_id)
    if task_info['method'] != 'build':
        raise koji.ImportError('task %s is not a build task' % task_id)
    if not task_params.get('opts', {}).get('scratch'):
        raise koji.ImportError('task %s is not a scratch build' % task_id)

    # sanity check the task, and extract data required for import
    srpm = None
    tasks = {}
    for child in task.getChildren():
        if child['method'] != 'buildArch':
            continue
        info = {'rpms': [],
                'logs': []}
        for output in list_task_output(child['id']):
            if output.endswith('.src.rpm'):
                srpm_name = os.path.basename(output)
                if not srpm:
                    srpm = srpm_name
                else:
                    if srpm != srpm_name:
                        raise koji.ImportError('task srpm names do not match: %s, %s' %
                                               (srpm, srpm_name))
            elif output.endswith('.noarch.rpm'):
                continue
            elif output.endswith('.rpm'):
                rpminfo = koji.parse_NVRA(os.path.basename(output))
                if 'arch' not in info:
                    info['arch'] = rpminfo['arch']
                elif info['arch'] != rpminfo['arch']:
                    raise koji.ImportError('multiple arches generated by task %s: %s, %s' %
                                           (child['id'], info['arch'], rpminfo['arch']))
                info['rpms'].append(output)
            elif output.endswith('.log'):
                info['logs'].append(output)
        if not info['rpms']:
            continue
        if not info['logs']:
            raise koji.ImportError('task %s is missing logs' % child['id'])
        buildroots = query_buildroots(taskID=child['id'],
                                      queryOpts={'order': '-id', 'limit': 1})
        if not buildroots:
            raise koji.ImportError('no buildroot associated with task %s' % child['id'])
        info['buildroot_id'] = buildroots[0]['id']
        tasks[child['id']] = info
    if not tasks:
        raise koji.ImportError('nothing to do for task %s' % task_id)

    # sanity check the build
    build_nvr = koji.parse_NVRA(srpm)
    build = get_build(build_nvr)
    if not build:
        raise koji.ImportError('no such build: %(name)s-%(version)s-%(release)s' %
                               build_nvr)
    if build['state'] != koji.BUILD_STATES['COMPLETE']:
        raise koji.ImportError('%s did not complete successfully' % build['nvr'])
    if not build['task_id']:
        raise koji.ImportError('no task for %s' % build['nvr'])
    # Intentionally skip checking the build task state.
    # There are cases where the build can be valid even though the task has failed,
    # e.g. tagging failures.

    # Compare SCM URLs only if build from an SCM
    build_task_info = Task(build['task_id']).getInfo(request=True)
    build_task_params = koji.tasks.parse_task_params(build_task_info['method'],
                                                     build_task_info['request'])
    if 'src' in task_params and SCM.is_scm_url(task_params['src']):
        # compare the task and build and make sure they are compatible with importing
        if task_params['src'] != build_task_params['src']:
            raise koji.ImportError('SCM URLs for the task and build do not match: %s, %s' %
                                   (task_params['src'], build_task_params['src']))
    build_arches = set()
    for rpminfo in list_rpms(buildID=build['id']):
        if rpminfo['arch'] == 'src':
            build_srpm = '%s.src.rpm' % rpminfo['nvr']
            if srpm != build_srpm:
                raise koji.ImportError('task and build srpm names do not match: %s, %s' %
                                       (srpm, build_srpm))
        elif rpminfo['arch'] == 'noarch':
            continue
        else:
            build_arches.add(rpminfo['arch'])
    if not build_arches:
        raise koji.ImportError('no arch-specific rpms found for %s' % build['nvr'])
    task_arches = set([t['arch'] for t in tasks.values()])
    overlapping_arches = task_arches.intersection(build_arches)
    if overlapping_arches:
        raise koji.ImportError('task %s and %s produce rpms with the same arches: %s' %
                               (task_info['id'], build['nvr'], ', '.join(overlapping_arches)))

    # everything looks good, do the import
    for task_id, info in tasks.items():
        taskpath = koji.pathinfo.task(task_id)
        for filename in info['rpms']:
            filepath = os.path.realpath(joinpath(taskpath, filename))
            rpminfo = import_rpm(filepath, build, info['buildroot_id'])
            import_rpm_file(filepath, build, rpminfo)
            add_rpm_sig(rpminfo['id'], koji.rip_rpm_sighdr(filepath))
        for logname in info['logs']:
            logpath = os.path.realpath(joinpath(taskpath, logname))
            import_build_log(logpath, build, subdir=info['arch'])

    # flag tags whose content has changed, so relevant repos can be regen'ed
    for tag in list_tags(build=build['id']):
        set_tag_update(tag['id'], 'IMPORT')

    return build['id']


def get_archive_types():
    """Return a list of all supported archive types."""
    select = """SELECT id, name, description, extensions FROM archivetypes
    ORDER BY id"""
    return _multiRow(select, {}, ('id', 'name', 'description', 'extensions'))


def _get_archive_type_by_name(name, strict=True):
    select = """SELECT id, name, description, extensions FROM archivetypes
    WHERE name = %(name)s"""
    return _singleRow(select, locals(), ('id', 'name', 'description', 'extensions'), strict)


def _get_archive_type_by_id(type_id, strict=False):
    select = """SELECT id, name, description, extensions FROM archivetypes
    WHERE id = %(type_id)i"""
    return _singleRow(select, locals(), ('id', 'name', 'description', 'extensions'), strict)


def get_archive_type(filename=None, type_name=None, type_id=None, strict=False):
    """
    Get the archive type for the given filename, type_name, or type_id.
    """
    if type_id:
        return _get_archive_type_by_id(type_id, strict)
    elif type_name:
        return _get_archive_type_by_name(type_name, strict)
    elif filename:
        # we handle that below
        pass
    else:
        raise koji.GenericError('one of filename, type_name, or type_id must be specified')

    parts = filename.split('.')
    query = QueryProcessor(
        tables=['archivetypes'],
        columns=['id', 'name', 'description', 'extensions'],
        clauses=['extensions ~* %(pattern)s'],
    )
    for start in range(len(parts) - 1, -1, -1):
        ext = '.'.join(parts[start:])
        query.values['pattern'] = r'(\s|^)%s(\s|$)' % ext
        results = query.execute()

        if len(results) == 1:
            return results[0]
        elif len(results) > 1:
            # this should never happen, and is a misconfiguration in the database
            raise koji.GenericError('multiple matches for file extension: %s' % ext)
    # otherwise
    if strict:
        raise koji.GenericError('unsupported file extension: %s' % ext)
    else:
        return None


def add_archive_type(name, description, extensions):
    """
    Add new archive type.

    Use this to tell Koji about new builds' files' extensions before
    importing the files.

    :param str name: archive type name, eg. "yaml"
    :param str description: eg. "YAML Ain't Markup Language"
    :param str extensions: space-separated list of descriptions, eg. "yaml yml"
    """
    context.session.assertPerm('admin')
    data = {'name': name,
            'description': description,
            'extensions': extensions,
            }
    if get_archive_type(type_name=name):
        raise koji.GenericError("archivetype %s already exists" % name)
    # No invalid or duplicate extensions
    for ext in extensions.split(' '):
        if not ext.replace('.', '').isalnum():
            raise koji.GenericError('invalid %s file extension' % ext)
        select = r"""SELECT id FROM archivetypes
                      WHERE extensions ~* E'(\\s|^)%s(\\s|$)'""" % ext
        results = _multiRow(select, {}, ('id',))
        if len(results) > 0:
            raise koji.GenericError('file extension %s already exists' % ext)
    insert = InsertProcessor('archivetypes', data=data)
    insert.execute()


def new_maven_build(build, maven_info):
    """
    Add Maven metadata to an existing build.
    maven_info must contain the 'group_id',
    'artifact_id', and 'version' keys.
    """
    maven_info = maven_info.copy()

    current_maven_info = get_maven_build(build)
    if current_maven_info:
        # already exists, verify that it matches
        for field in ('group_id', 'artifact_id', 'version'):
            if current_maven_info[field] != maven_info[field]:
                raise koji.BuildError('%s mismatch (current: %s, new: %s)' %
                                      (field, current_maven_info[field], maven_info[field]))
    else:
        maven_info['build_id'] = build['id']
        data = dslice(maven_info, ['build_id', 'group_id', 'artifact_id', 'version'])
        insert = InsertProcessor('maven_builds', data=data)
        insert.execute()
        # also add build_types entry
        new_typed_build(build, 'maven')


def new_win_build(build_info, win_info):
    """
    Add Windows metadata to an existing build.
    win_info must contain a 'platform' key.
    """
    build_id = build_info['id']
    current = get_win_build(build_id, strict=False)
    if current:
        if current['platform'] != win_info['platform']:
            update = UpdateProcessor('win_builds', clauses=['build_id=%(build_id)i'],
                                     values={'build_id': build_id})
            update.set(platform=win_info['platform'])
            update.execute()
    else:
        insert = InsertProcessor('win_builds')
        insert.set(build_id=build_id)
        insert.set(platform=win_info['platform'])
        insert.execute()
        # also add build_types entry
        new_typed_build(build_info, 'win')


def new_image_build(build_info):
    """
    Added Image metadata to an existing build. This is just the buildid so that
    we can distinguish image builds from other types.
    """
    # We don't have to worry about updating an image build because the id is
    # the only thing we care about, and that should never change if a build
    # fails first and succeeds later on a resubmission.
    query = QueryProcessor(tables=('image_builds',), columns=('build_id',),
                           clauses=('build_id = %(build_id)i',),
                           values={'build_id': build_info['id']})
    result = query.executeOne()
    if not result:
        insert = InsertProcessor('image_builds')
        insert.set(build_id=build_info['id'])
        insert.execute()
        # also add build_types entry
        new_typed_build(build_info, 'image')


def new_typed_build(build_info, btype):
    """Mark build as a given btype"""

    btype_id = lookup_name('btype', btype, strict=True)['id']
    query = QueryProcessor(tables=('build_types',), columns=('build_id',),
                           clauses=('build_id = %(build_id)i',
                                    'btype_id = %(btype_id)i',),
                           values={'build_id': build_info['id'],
                                   'btype_id': btype_id})
    result = query.executeOne()
    if not result:
        insert = InsertProcessor('build_types')
        insert.set(build_id=build_info['id'])
        insert.set(btype_id=btype_id)
        insert.execute()


def import_archive(filepath, buildinfo, type, typeInfo, buildroot_id=None):
    """
    Import an archive file and associate it with a build.  The archive can
    be any non-rpm filetype supported by Koji.

    This wraps import_archive_internal and limits options
    """

    return import_archive_internal(filepath, buildinfo, type, typeInfo, buildroot_id=None)


def import_archive_internal(filepath, buildinfo, type, typeInfo, buildroot_id=None, fileinfo=None):
    """
    Import an archive file and associate it with a build.  The archive can
    be any non-rpm filetype supported by Koji.

    filepath: full path to the archive file
    buildinfo: dict of information about the build to associate the archive with
               (as returned by getBuild())
    type: type of the archive being imported.  Currently supported archive types: maven, win, image
    typeInfo: dict of type-specific information
    buildroot_id: the id of the buildroot the archive was built in (may be None)
    fileinfo: content generator metadata for file (may be None)
    """

    if fileinfo is None:
        fileinfo = {}
    metadata_only = fileinfo.get('metadata_only', False)

    if metadata_only:
        filepath = None
    elif not os.path.exists(filepath):
        raise koji.GenericError('no such file: %s' % filepath)

    archiveinfo = {'buildroot_id': buildroot_id}
    archiveinfo['build_id'] = buildinfo['id']
    if metadata_only:
        filename = koji.fixEncoding(fileinfo['filename'])
        archiveinfo['filename'] = filename
        archiveinfo['size'] = fileinfo['filesize']
        archiveinfo['checksum'] = fileinfo['checksum']
        if fileinfo['checksum_type'] not in ('md5', 'sha256'):
            raise koji.GenericError("Unsupported checksum type: %(checksum_type)s" % fileinfo)
        archiveinfo['checksum_type'] = koji.CHECKSUM_TYPES[fileinfo['checksum_type']]
        archiveinfo['metadata_only'] = True
    else:
        filename = koji.fixEncoding(os.path.basename(filepath))
        archiveinfo['filename'] = filename
        archiveinfo['size'] = os.path.getsize(filepath)
        # trust values computed on hub (CG_Importer.prep_outputs)
        if not fileinfo or not fileinfo.get('hub.checked_hash'):
            with open(filepath, 'rb') as archivefp:
                chksum = get_verify_class('sha256')()
                while True:
                    contents = archivefp.read(8192)
                    if not contents:
                        break
                    chksum.update(contents)
            archiveinfo['checksum'] = chksum.hexdigest()
            archiveinfo['checksum_type'] = koji.CHECKSUM_TYPES['sha256']
        else:
            archiveinfo['checksum'] = fileinfo['checksum']
            archiveinfo['checksum_type'] = koji.CHECKSUM_TYPES[fileinfo['checksum_type']]
        if fileinfo:
            # check against metadata
            if archiveinfo['size'] != fileinfo['filesize']:
                raise koji.GenericError("File size mismatch for %s: %s != %s" %
                                        (filename, archiveinfo['size'], fileinfo['filesize']))
            if (archiveinfo['checksum'] != fileinfo['checksum'] or
                    archiveinfo['checksum_type'] != koji.CHECKSUM_TYPES[
                        fileinfo['checksum_type']]):
                raise koji.GenericError("File checksum mismatch for %s: %s != %s" %
                                        (filename, archiveinfo['checksum'], fileinfo['checksum']))
    archivetype = get_archive_type(filename, strict=True)
    archiveinfo['type_id'] = archivetype['id']
    btype = lookup_name('btype', type, strict=False)
    if btype is None:
        raise koji.BuildError('unsupported build type: %s' % type)
    if btype['name'] not in get_build_type(buildinfo, strict=True):
        raise koji.ImportError('Build does not have type %s' % btype['name'])
    archiveinfo['btype_id'] = btype['id']

    # cg extra data
    extra = fileinfo.get('extra', None)
    if extra is not None:
        archiveinfo['extra'] = json.dumps(extra)

    koji.plugin.run_callbacks('preImport', type='archive', archive=archiveinfo, build=buildinfo,
                              build_type=type, filepath=filepath, fileinfo=fileinfo)

    # XXX verify that the buildroot is associated with a task that's associated with the build
    archive_id = nextval('archiveinfo_id_seq')
    archiveinfo['id'] = archive_id
    insert = InsertProcessor('archiveinfo', data=archiveinfo)
    insert.execute()

    if type == 'maven':
        get_maven_build(buildinfo, strict=True)  # raise exception if not found

        if archivetype['name'] == 'pom' and not metadata_only:
            pom_info = koji.parse_pom(filepath)
            pom_maveninfo = koji.pom_to_maven_info(pom_info)
            # sanity check: Maven info from pom must match the user-supplied typeInfo
            if koji.mavenLabel(pom_maveninfo) != koji.mavenLabel(typeInfo):
                raise koji.BuildError(
                    'Maven info from .pom file (%s) does not match user-supplied typeInfo (%s)' %
                    (koji.mavenLabel(pom_maveninfo), koji.mavenLabel(typeInfo)))
            # sanity check: the filename of the pom file must match <artifactId>-<version>.pom
            if filename != '%(artifact_id)s-%(version)s.pom' % typeInfo:
                raise koji.BuildError('Maven info (%s) is not consistent with pom filename (%s)' %
                                      (koji.mavenLabel(typeInfo), filename))

        insert = InsertProcessor('maven_archives',
                                 data=dslice(typeInfo, ('group_id', 'artifact_id', 'version')))
        insert.set(archive_id=archive_id)
        insert.execute()

        if not metadata_only:
            # move the file to it's final destination
            mavendir = joinpath(koji.pathinfo.mavenbuild(buildinfo),
                                koji.pathinfo.mavenrepo(typeInfo))
            _import_archive_file(filepath, mavendir)
            _generate_maven_metadata(mavendir)
    elif type == 'win':
        get_win_build(buildinfo, strict=True)  # raise exception if not found

        insert = InsertProcessor('win_archives')
        insert.set(archive_id=archive_id)
        relpath = typeInfo['relpath'].strip('/')
        insert.set(relpath=relpath)
        if not typeInfo['platforms']:
            raise koji.BuildError('no value for platforms')
        insert.set(platforms=' '.join(typeInfo['platforms']))
        if typeInfo['flags']:
            insert.set(flags=' '.join(typeInfo['flags']))
        insert.execute()

        if not metadata_only:
            destdir = koji.pathinfo.winbuild(buildinfo)
            if relpath:
                destdir = joinpath(destdir, relpath)
            _import_archive_file(filepath, destdir)
    elif type == 'image':
        insert = InsertProcessor('image_archives')
        insert.set(archive_id=archive_id)
        insert.set(arch=typeInfo['arch'])
        insert.execute()
        if not metadata_only:
            imgdir = joinpath(koji.pathinfo.imagebuild(buildinfo))
            _import_archive_file(filepath, imgdir)
        # import log files?
    else:
        # new style type, no supplementary table
        if not metadata_only:
            destdir = koji.pathinfo.typedir(buildinfo, btype['name'])
            _import_archive_file(filepath, destdir)

    archiveinfo = get_archive(archive_id, strict=True)
    koji.plugin.run_callbacks('postImport', type='archive', archive=archiveinfo, build=buildinfo,
                              build_type=type, filepath=filepath, fileinfo=fileinfo)
    return archiveinfo


def _import_archive_file(filepath, destdir):
    """
    Move the file to it's final location on the filesystem.
    filepath must exist, destdir will be created if it doesn not exist.
    A symlink pointing from the old location to the new location will
    be created.
    """
    fname = os.path.basename(filepath)
    fname = koji.fixEncoding(fname)
    final_path = "%s/%s" % (destdir, fname)
    if os.path.exists(final_path):
        raise koji.GenericError("Error importing archive file, %s already exists" % final_path)
    if os.path.islink(filepath) or not os.path.isfile(filepath):
        raise koji.GenericError("Error importing archive file, %s is not a regular file" %
                                filepath)
    move_and_symlink(filepath, final_path, create_dir=True)


def _generate_maven_metadata(mavendir):
    """
    Generate md5 and sha1 sums for every file in mavendir, if it doesn't already exist.
    Checksum files will be named <filename>.md5 and <filename>.sha1.
    """
    mavenfiles = os.listdir(mavendir)
    for mavenfile in mavenfiles:
        if os.path.splitext(mavenfile)[1] in ('.md5', '.sha1'):
            continue
        if not os.path.isfile('%s/%s' % (mavendir, mavenfile)):
            continue
        for ext, sum_constr in (('.md5', md5_constructor), ('.sha1', hashlib.sha1)):
            sumfile = mavenfile + ext
            if sumfile not in mavenfiles:
                sum = sum_constr()
                with open('%s/%s' % (mavendir, mavenfile), 'rb') as fobj:
                    while True:
                        content = fobj.read(8192)
                        if not content:
                            break
                        sum.update(content)
                with open('%s/%s' % (mavendir, sumfile), 'w') as sumobj:
                    sumobj.write(sum.hexdigest())


def add_rpm_sig(an_rpm, sighdr):
    """Store a signature header for an rpm"""
    # calling function should perform permission checks, if applicable
    rinfo = get_rpm(an_rpm, strict=True)
    if rinfo['external_repo_id']:
        raise koji.GenericError("Not an internal rpm: %s (from %s)"
                                % (an_rpm, rinfo['external_repo_name']))
    binfo = get_build(rinfo['build_id'])
    builddir = koji.pathinfo.build(binfo)
    if not os.path.isdir(builddir):
        raise koji.GenericError("No such directory: %s" % builddir)
    rawhdr = koji.RawHeader(sighdr)
    sigmd5 = koji.hex_string(rawhdr.get(koji.RPM_SIGTAG_MD5))
    if sigmd5 == rinfo['payloadhash']:
        # note: payloadhash is a misnomer, that field is populated with sigmd5.
        sigkey = rawhdr.get(koji.RPM_SIGTAG_GPG)
        if not sigkey:
            sigkey = rawhdr.get(koji.RPM_SIGTAG_PGP)
    else:
        # In older rpms, this field in the signature header does not actually match
        # sigmd5 (I think rpmlib pulls it from SIGTAG_GPG). Anyway, this
        # sanity check fails incorrectly for those rpms, so we fall back to
        # a somewhat more expensive check.
        # ALSO, for these older rpms, the layout of SIGTAG_GPG is different too, so
        # we need to pull that differently as well
        rpm_path = "%s/%s" % (builddir, koji.pathinfo.rpm(rinfo))
        sigmd5, sigkey = _scan_sighdr(sighdr, rpm_path)
        sigmd5 = koji.hex_string(sigmd5)
        if sigmd5 != rinfo['payloadhash']:
            nvra = "%(name)s-%(version)s-%(release)s.%(arch)s" % rinfo
            raise koji.GenericError("wrong md5 for %s: %s" % (nvra, sigmd5))
    if not sigkey:
        sigkey = ''
        # we use the sigkey='' to represent unsigned in the db (so that uniqueness works)
    else:
        sigkey = koji.get_sigpacket_key_id(sigkey)
    sighash = md5_constructor(sighdr).hexdigest()
    rpm_id = rinfo['id']
    # - db entry
    q = """SELECT sighash FROM rpmsigs WHERE rpm_id=%(rpm_id)i AND sigkey=%(sigkey)s"""
    rows = _fetchMulti(q, locals())
    if rows:
        # TODO[?] - if sighash is the same, handle more gracefully
        nvra = "%(name)s-%(version)s-%(release)s.%(arch)s" % rinfo
        raise koji.GenericError("Signature already exists for package %s, key %s" % (nvra, sigkey))
    koji.plugin.run_callbacks('preRPMSign', sigkey=sigkey, sighash=sighash, build=binfo, rpm=rinfo)
    insert = """INSERT INTO rpmsigs(rpm_id, sigkey, sighash)
    VALUES (%(rpm_id)s, %(sigkey)s, %(sighash)s)"""
    _dml(insert, locals())
    # - write to fs
    sigpath = "%s/%s" % (builddir, koji.pathinfo.sighdr(rinfo, sigkey))
    koji.ensuredir(os.path.dirname(sigpath))
    with open(sigpath, 'wb') as fo:
        fo.write(sighdr)
    koji.plugin.run_callbacks('postRPMSign',
                              sigkey=sigkey, sighash=sighash, build=binfo, rpm=rinfo)


def _scan_sighdr(sighdr, fn):
    """Splices sighdr with other headers from fn and queries (no payload)"""
    # This is hackish, but it works
    if not os.path.exists(fn):
        raise koji.GenericError("No such path: %s" % fn)
    if not os.path.isfile(fn):
        raise koji.GenericError("Not a regular file: %s" % fn)
    # XXX should probably add an option to splice_rpm_sighdr to handle this instead
    sig_start, sigsize = koji.find_rpm_sighdr(fn)
    hdr_start = sig_start + sigsize
    hdrsize = koji.rpm_hdr_size(fn, hdr_start)
    inp = open(fn, 'rb')
    outp = tempfile.TemporaryFile(mode='w+b')
    # before signature
    outp.write(inp.read(sig_start))
    # signature
    outp.write(sighdr)
    inp.seek(sigsize, 1)
    # main header
    outp.write(inp.read(hdrsize))
    inp.close()
    outp.seek(0, 0)
    ts = rpm.TransactionSet()
    ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES | rpm._RPMVSF_NODIGESTS)
    # (we have no payload, so verifies would fail otherwise)
    hdr = ts.hdrFromFdno(outp.fileno())
    outp.close()
    sig = koji.get_header_field(hdr, 'siggpg')
    if not sig:
        sig = koji.get_header_field(hdr, 'sigpgp')
    return koji.get_header_field(hdr, 'sigmd5'), sig


def check_rpm_sig(an_rpm, sigkey, sighdr):
    # verify that the provided signature header matches the key and rpm
    rinfo = get_rpm(an_rpm, strict=True)
    binfo = get_build(rinfo['build_id'])
    builddir = koji.pathinfo.build(binfo)
    rpm_path = "%s/%s" % (builddir, koji.pathinfo.rpm(rinfo))
    if not os.path.exists(rpm_path):
        raise koji.GenericError("No such path: %s" % rpm_path)
    if not os.path.isfile(rpm_path):
        raise koji.GenericError("Not a regular file: %s" % rpm_path)
    fd, temp = tempfile.mkstemp()
    os.close(fd)
    try:
        koji.splice_rpm_sighdr(sighdr, rpm_path, temp)
        ts = rpm.TransactionSet()
        ts.setVSFlags(0)  # full verify
        with open(temp, 'rb') as fo:
            hdr = ts.hdrFromFdno(fo.fileno())
    except Exception:
        try:
            os.unlink(temp)
        except Exception:
            pass
        raise
    raw_key = koji.get_header_field(hdr, 'siggpg')
    if not raw_key:
        raw_key = koji.get_header_field(hdr, 'sigpgp')
    if not raw_key:
        found_key = None
    else:
        found_key = koji.get_sigpacket_key_id(raw_key)
    if sigkey != found_key:
        raise koji.GenericError("Signature key mismatch: got %s, expected %s"
                                % (found_key, sigkey))
    os.unlink(temp)


def query_rpm_sigs(rpm_id=None, sigkey=None, queryOpts=None):
    """Queries db for rpm signatures

    :param int rpm_id: rpm ID
    :param int sigkey: signature key hash
    :param queryOpts: query options used by the QueryProcessor.

    :returns: list of dicts (rpm_id, sigkey, sighash)
    """
    fields = ('rpm_id', 'sigkey', 'sighash')
    clauses = []
    if rpm_id is not None:
        clauses.append("rpm_id=%(rpm_id)s")
    if sigkey is not None:
        clauses.append("sigkey=%(sigkey)s")
    query = QueryProcessor(columns=fields, tables=('rpmsigs',), clauses=clauses,
                           values=locals(), opts=queryOpts)
    return query.execute()


def write_signed_rpm(an_rpm, sigkey, force=False):
    """Write a signed copy of the rpm"""
    rinfo = get_rpm(an_rpm, strict=True)
    if rinfo['external_repo_id']:
        raise koji.GenericError("Not an internal rpm: %s (from %s)"
                                % (an_rpm, rinfo['external_repo_name']))
    binfo = get_build(rinfo['build_id'])
    nvra = "%(name)s-%(version)s-%(release)s.%(arch)s" % rinfo
    builddir = koji.pathinfo.build(binfo)
    rpm_path = "%s/%s" % (builddir, koji.pathinfo.rpm(rinfo))
    if not os.path.exists(rpm_path):
        raise koji.GenericError("No such path: %s" % rpm_path)
    if not os.path.isfile(rpm_path):
        raise koji.GenericError("Not a regular file: %s" % rpm_path)
    # make sure we have it in the db
    rpm_id = rinfo['id']
    q = """SELECT sighash FROM rpmsigs WHERE rpm_id=%(rpm_id)i AND sigkey=%(sigkey)s"""
    row = _fetchSingle(q, locals())
    if not row:
        raise koji.GenericError("No cached signature for package %s, key %s" % (nvra, sigkey))
    (sighash,) = row
    signedpath = "%s/%s" % (builddir, koji.pathinfo.signed(rinfo, sigkey))
    if os.path.exists(signedpath):
        if not force:
            # already present
            return
        else:
            os.unlink(signedpath)
    sigpath = "%s/%s" % (builddir, koji.pathinfo.sighdr(rinfo, sigkey))
    with open(sigpath, 'rb') as fo:
        sighdr = fo.read()
    koji.ensuredir(os.path.dirname(signedpath))
    koji.splice_rpm_sighdr(sighdr, rpm_path, signedpath)


def query_history(tables=None, **kwargs):
    """Returns history data from various tables that support it

    tables: list of versioned tables to search, no value implies all tables
            valid entries: user_perms, user_groups, tag_inheritance, tag_config,
                build_target_config, external_repo_config, tag_external_repos,
                tag_listing, tag_packages, tag_package_owners, group_config,
                group_req_listing, group_package_listing

    - Time options -
    times are specified as an integer event or a string timestamp
    time options are valid for all record types
    before: either created or revoked before timestamp
    after: either created or revoked after timestamp
    beforeEvent: either created or revoked before event id
    afterEvent: either created or revoked after event id

    - other versioning options-
    active: select by active status
    editor: record created or revoked by user

    - table-specific search options -
    use of these options will implicitly limit the search to applicable tables
    package: only for given package
    build: only for given build
    tag: only for given tag
    user: only affecting a given user
    permission: only relating to a given permission
    external_repo: only relateing to an external repo
    build_target: only relating to a build target
    group: only relating to a (comps) group
    cg: only relating to a content generator
    """
    common_fields = {
        # fields:aliases common to all versioned tables
        'active': 'active',
        'create_event': 'create_event',
        'revoke_event': 'revoke_event',
        'creator_id': 'creator_id',
        'revoker_id': 'revoker_id',
    }
    common_joins = [
        "events AS ev1 ON ev1.id = create_event",
        "LEFT OUTER JOIN events AS ev2 ON ev2.id = revoke_event",
        "users AS creator ON creator.id = creator_id",
        "LEFT OUTER JOIN users AS revoker ON revoker.id = revoker_id",
    ]
    common_joined_fields = {
        'creator.name': 'creator_name',
        'revoker.name': 'revoker_name',
        'EXTRACT(EPOCH FROM ev1.time) AS create_ts': 'create_ts',
        'EXTRACT(EPOCH FROM ev2.time) AS revoke_ts': 'revoke_ts',
    }
    table_fields = {
        'user_perms': ['user_id', 'perm_id'],
        'user_groups': ['user_id', 'group_id'],
        'cg_users': ['user_id', 'cg_id'],
        'tag_inheritance': ['tag_id', 'parent_id', 'priority', 'maxdepth', 'intransitive',
                            'noconfig', 'pkg_filter'],
        'tag_config': ['tag_id', 'arches', 'perm_id', 'locked', 'maven_support',
                       'maven_include_all'],
        'tag_extra': ['tag_id', 'key', 'value'],
        'build_target_config': ['build_target_id', 'build_tag', 'dest_tag'],
        'external_repo_config': ['external_repo_id', 'url'],
        'host_config': ['host_id', 'arches', 'capacity', 'description', 'comment', 'enabled'],
        'host_channels': ['host_id', 'channel_id'],
        'tag_external_repos': ['tag_id', 'external_repo_id', 'priority', 'merge_mode'],
        'tag_listing': ['build_id', 'tag_id'],
        'tag_packages': ['package_id', 'tag_id', 'blocked', 'extra_arches'],
        'tag_package_owners': ['package_id', 'tag_id', 'owner'],
        'group_config': ['group_id', 'tag_id', 'blocked', 'exported', 'display_name', 'is_default',
                         'uservisible', 'description', 'langonly', 'biarchonly'],
        'group_req_listing': ['group_id', 'tag_id', 'req_id', 'blocked', 'type', 'is_metapkg'],
        'group_package_listing': ['group_id', 'tag_id', 'package', 'blocked', 'type',
                                  'basearchonly', 'requires'],
    }
    name_joins = {
        # joins triggered by table fields for name lookup
        # field : [table, join-alias, alias]
        'user_id': ['users', 'users', 'user'],
        'perm_id': ['permissions', 'permission'],
        'cg_id': ['content_generator'],
        # group_id is overloaded (special case below)
        'tag_id': ['tag'],
        'host_id': ['host'],
        'channel_id': ['channels'],
        'parent_id': ['tag', 'parent'],
        'build_target_id': ['build_target'],
        'build_tag': ['tag', 'build_tag'],
        'dest_tag': ['tag', 'dest_tag'],
        'external_repo_id': ['external_repo'],
        # build_id is special cased
        'package_id': ['package'],
        'owner': ['users', 'owner'],
        'req_id': ['groups', 'req'],
    }
    if tables is None:
        tables = sorted(table_fields.keys())
    else:
        for table in tables:
            if table not in table_fields:
                raise koji.GenericError("Unknown history table: %s" % table)
    ret = {}
    for table in tables:
        fields = {}
        for field in common_fields:
            fullname = "%s.%s" % (table, field)
            fields[fullname] = common_fields[field]
        joins = list(common_joins)
        fields.update(common_joined_fields)
        joined = {}
        for field in table_fields[table]:
            fullname = "%s.%s" % (table, field)
            fields[fullname] = field
            name_join = name_joins.get(field)
            if name_join:
                tbl = join_as = name_join[0]
                if len(name_join) > 1:
                    join_as = name_join[1]
                joined[tbl] = join_as
                fullname = "%s.name" % join_as
                if len(name_join) > 2:
                    # apply alias
                    fields[fullname] = "%s.name" % name_join[2]
                else:
                    fields[fullname] = fullname
                if join_as == tbl:
                    joins.append('LEFT OUTER JOIN %s ON %s = %s.id' % (tbl, field, tbl))
                else:
                    joins.append('LEFT OUTER JOIN %s AS %s ON %s = %s.id' %
                                 (tbl, join_as, field, join_as))
            elif field == 'build_id':
                # special case
                fields.update({
                    'package.name': 'name',  # XXX?
                    'build.version': 'version',
                    'build.release': 'release',
                    'build.epoch': 'epoch',
                    'build.state': 'build.state',
                })
                joins.extend([
                    'build ON build_id = build.id',
                    'package ON build.pkg_id = package.id',
                ])
                joined['build'] = 'build'
                joined['package'] = 'package'
            elif field == 'group_id':
                if table.startswith('group_'):
                    fields['groups.name'] = 'group.name'
                    joins.append('groups ON group_id = groups.id')
                    joined['groups'] = 'groups'
                elif table == 'user_groups':
                    fields['usergroup.name'] = 'group.name'
                    joins.append('users AS usergroup ON group_id = usergroup.id')
                    joined['users'] = 'usergroup'
        clauses = []
        skip = False
        data = {}
        for arg in kwargs:
            value = kwargs[arg]
            if arg == 'tag':
                if 'tag' not in joined:
                    skip = True
                    break
                data['tag_id'] = get_tag_id(value, strict=True)
                if table == 'tag_inheritance':
                    # special cased because there are two tag columns
                    clauses.append("tag_id = %(tag_id)i OR parent_id = %(tag_id)i")
                else:
                    clauses.append("%s.id = %%(tag_id)i" % joined['tag'])
            elif arg == 'build':
                if 'build' not in joined:
                    skip = True
                    break
                data['build_id'] = get_build(value, strict=True)['id']
                clauses.append("build.id = %(build_id)i")
            elif arg == 'host':
                if 'host' not in joined:
                    skip = True
                    break
                data['host_id'] = get_id('host', value, strict=False)
                clauses.append("host.id = %(host_id)i")
            elif arg == 'channel':
                if 'channels' not in joined:
                    skip = True
                    break
                data['channel_id'] = get_id('channels', value, strict=False)
                clauses.append("channels.id = %(channel_id)i")
            elif arg == 'package':
                pkg_field_name = "%s.package" % table
                if 'package' in joined:
                    data['pkg_id'] = get_package_id(value, strict=True)
                    clauses.append("package.id = %(pkg_id)i")
                elif pkg_field_name in fields:
                    # e.g. group_package_listing
                    data['group_package'] = str(value)
                    clauses.append("%s = %%(group_package)s" % pkg_field_name)
                else:
                    skip = True
                    break
            elif arg == 'user':
                if 'users' not in joined:
                    skip = True
                    break
                data['affected_user_id'] = get_user(value, strict=True)['id']
                clauses.append("%s.id = %%(affected_user_id)i" % joined['users'])
            elif arg == 'permission':
                if 'permissions' not in joined:
                    skip = True
                    break
                data['perm_id'] = get_perm_id(value, strict=True)
                clauses.append("%s.id = %%(perm_id)i" % joined['permissions'])
            elif arg == 'cg':
                if 'content_generator' not in joined:
                    skip = True
                    break
                data['cg_id'] = lookup_name('content_generator', value, strict=True)['id']
                clauses.append("%s.id = %%(cg_id)i" % joined['content_generator'])
            elif arg == 'external_repo':
                if 'external_repo' not in joined:
                    skip = True
                    break
                data['external_repo_id'] = get_external_repo_id(value, strict=True)
                clauses.append("%s.id = %%(external_repo_id)i" % joined['external_repo'])
            elif arg == 'build_target':
                if 'build_target' not in joined:
                    skip = True
                    break
                data['build_target_id'] = get_build_target_id(value, strict=True)
                clauses.append("%s.id = %%(build_target_id)i" % joined['build_target'])
            elif arg == 'group':
                if 'groups' not in joined:
                    skip = True
                    break
                data['group_id'] = get_group_id(value, strict=True)
                clauses.append("%s.id = %%(group_id)i" % joined['groups'])
            elif arg == 'active':
                if value:
                    clauses.append('active = TRUE')
                elif value is not None:
                    clauses.append('active IS NULL')
            elif arg == 'editor':
                data['editor'] = get_user(value, strict=True)['id']
                clauses.append('creator.id = %(editor)i OR revoker.id = %(editor)i')
                fields['creator.id = %(editor)i'] = '_created_by'
                fields['revoker.id = %(editor)i'] = '_revoked_by'
            elif arg == 'after':
                if not isinstance(value, str):
                    value = datetime.datetime.fromtimestamp(value).isoformat(' ')
                data['after'] = value
                clauses.append('ev1.time > %(after)s OR ev2.time > %(after)s')
                fields['ev1.time > %(after)s'] = '_created_after'
                fields['ev2.time > %(after)s'] = '_revoked_after'
                # clauses.append('EXTRACT(EPOCH FROM ev1.time) > %(after)s OR '
                #                'EXTRACT(EPOCH FROM ev2.time) > %(after)s')
            elif arg == 'afterEvent':
                data['afterEvent'] = value
                c_test = '%s.create_event > %%(afterEvent)i' % table
                r_test = '%s.revoke_event > %%(afterEvent)i' % table
                clauses.append(' OR '.join([c_test, r_test]))
                fields[c_test] = '_created_after_event'
                fields[r_test] = '_revoked_after_event'
            elif arg == 'before':
                if not isinstance(value, str):
                    value = datetime.datetime.fromtimestamp(value).isoformat(' ')
                data['before'] = value
                clauses.append('ev1.time < %(before)s OR ev2.time < %(before)s')
                # clauses.append('EXTRACT(EPOCH FROM ev1.time) < %(before)s OR '
                #                'EXTRACT(EPOCH FROM ev2.time) < %(before)s')
                fields['ev1.time < %(before)s'] = '_created_before'
                fields['ev2.time < %(before)s'] = '_revoked_before'
            elif arg == 'beforeEvent':
                data['beforeEvent'] = value
                c_test = '%s.create_event < %%(beforeEvent)i' % table
                r_test = '%s.revoke_event < %%(beforeEvent)i' % table
                clauses.append(' OR '.join([c_test, r_test]))
                fields[c_test] = '_created_before_event'
                fields[r_test] = '_revoked_before_event'
        if skip:
            continue
        fields, aliases = zip(*fields.items())
        query = QueryProcessor(columns=fields, aliases=aliases, tables=[table],
                               joins=joins, clauses=clauses, values=data)
        ret[table] = query.iterate()
    return ret


def tag_history(build=None, tag=None, package=None, active=None, queryOpts=None):
    """Returns historical tag data

    package: only for given package
    build: only for given build
    tag: only for given tag

    Deprecated; will be removed in a future version
    See: https://pagure.io/koji/issue/836
    """
    logger.warning("The tag_history call is deprecated and will be removed in a future version.")
    fields = ('build.id', 'package.name', 'build.version', 'build.release',
              'tag.id', 'tag.name', 'tag_listing.active',
              'tag_listing.create_event', 'tag_listing.revoke_event',
              'tag_listing.creator_id', 'tag_listing.revoker_id',
              'creator.name', 'revoker.name',
              'EXTRACT(EPOCH FROM ev1.time)', 'EXTRACT(EPOCH FROM ev2.time)',
              'maven_builds.build_id', 'win_builds.build_id')
    aliases = ('build_id', 'name', 'version', 'release',
               'tag_id', 'tag_name', 'active',
               'create_event', 'revoke_event',
               'creator_id', 'revoker_id',
               'creator_name', 'revoker_name',
               'create_ts', 'revoke_ts',
               'maven_build_id', 'win_build_id')
    st_complete = koji.BUILD_STATES['COMPLETE']
    tables = ['tag_listing']
    joins = ["tag ON tag.id = tag_listing.tag_id",
             "build ON build.id = tag_listing.build_id",
             "package ON package.id = build.pkg_id",
             "events AS ev1 ON ev1.id = tag_listing.create_event",
             "LEFT OUTER JOIN events AS ev2 ON ev2.id = tag_listing.revoke_event",
             "users AS creator ON creator.id = tag_listing.creator_id",
             "LEFT OUTER JOIN users AS revoker ON revoker.id = tag_listing.revoker_id",
             "LEFT OUTER JOIN maven_builds ON maven_builds.build_id = build.id",
             "LEFT OUTER JOIN win_builds ON win_builds.build_id = build.id"]
    clauses = []
    if tag is not None:
        tag_id = get_tag_id(tag, strict=True)
        clauses.append("tag.id = %(tag_id)i")
    if build is not None:
        build_id = get_build(build, strict=True)['id']
        clauses.append("build.id = %(build_id)i")
    if package is not None:
        pkg_id = get_package_id(package, strict=True)
        clauses.append("package.id = %(pkg_id)i")
    if active is True:
        clauses.append("tag_listing.active is true")
    elif active is False:
        clauses.append("tag_listing.active is not true")
    query = QueryProcessor(columns=fields, aliases=aliases, tables=tables,
                           joins=joins, clauses=clauses, values=locals(),
                           opts=queryOpts)
    return query.iterate()


def untagged_builds(name=None, queryOpts=None):
    """Returns the list of untagged builds"""
    fields = ('build.id', 'package.name', 'build.version', 'build.release')
    aliases = ('id', 'name', 'version', 'release')
    st_complete = koji.BUILD_STATES['COMPLETE']
    tables = ('build',)
    joins = []
    if name is None:
        joins.append("""package ON package.id = build.pkg_id""")
    else:
        joins.append("""package ON package.name=%(name)s AND package.id = build.pkg_id""")
    joins.append("""LEFT OUTER JOIN tag_listing ON tag_listing.build_id = build.id
                    AND tag_listing.active = TRUE""")
    clauses = ["tag_listing.tag_id IS NULL", "build.state = %(st_complete)i"]
    # q = """SELECT build.id, package.name, build.version, build.release
    # FROM build
    #    JOIN package on package.id = build.pkg_id
    #    LEFT OUTER JOIN tag_listing ON tag_listing.build_id = build.id
    #        AND tag_listing.active IS TRUE
    # WHERE tag_listing.tag_id IS NULL AND build.state = %(st_complete)i"""
    # return _multiRow(q, locals(), aliases)
    query = QueryProcessor(columns=fields, aliases=aliases, tables=tables,
                           joins=joins, clauses=clauses, values=locals(),
                           opts=queryOpts)
    return query.iterate()


def build_references(build_id, limit=None, lazy=False):
    """Returns references to a build

    This call is used to determine whether a build can be deleted

    :param int build_id: numeric build id
    :param int limit: If given, only return up to N results of each ref type
    :param bool lazy: If true, stop when any reference is found

    :returns: dict of reference results for each reference type
    """

    ret = {}

    # find tags
    q = """SELECT tag_id, tag.name FROM tag_listing JOIN tag on tag_id = tag.id
    WHERE build_id = %(build_id)i AND active = TRUE"""
    ret['tags'] = _multiRow(q, locals(), ('id', 'name'))

    if lazy and ret['tags']:
        return ret

    # we'll need the component rpm and archive ids for the rest
    q = """SELECT id FROM rpminfo WHERE build_id=%(build_id)i"""
    build_rpm_ids = _fetchMulti(q, locals())
    q = """SELECT id FROM archiveinfo WHERE build_id=%(build_id)i"""
    build_archive_ids = _fetchMulti(q, locals())

    # find rpms whose buildroots we were in
    st_complete = koji.BUILD_STATES['COMPLETE']
    fields = ('id', 'name', 'version', 'release', 'arch', 'build_id')
    idx = {}
    q = """SELECT
        rpminfo.id, rpminfo.name, rpminfo.version, rpminfo.release, rpminfo.arch, rpminfo.build_id
    FROM rpminfo, build
    WHERE
        rpminfo.buildroot_id IN (
            SELECT DISTINCT buildroot_id
                FROM buildroot_listing
                WHERE rpm_id = %(rpm_id)s)
        AND rpminfo.build_id = build.id
        AND build.state = %(st_complete)i"""
    if limit is not None:
        q += "\nLIMIT %(limit)i"
    for (rpm_id,) in build_rpm_ids:
        for row in _multiRow(q, locals(), fields):
            idx.setdefault(row['id'], row)
        if limit is not None and len(idx) > limit:
            break
    ret['rpms'] = to_list(idx.values())

    if lazy and ret['rpms']:
        return ret

    ret['component_of'] = []
    # find images/archives that contain the build rpms
    fields = ['archive_id']
    joins = ['archiveinfo on archiveinfo.id = archive_id',
             'build on archiveinfo.build_id = build.id']
    clauses = ['archive_rpm_components.rpm_id = %(rpm_id)s',
               'build.state = %(st_complete)s']
    values = {'st_complete': koji.BUILD_STATES['COMPLETE']}
    qopts = {'asList': True}
    if limit:
        qopts['limit'] = limit
    query = QueryProcessor(columns=fields, tables=['archive_rpm_components'],
                           clauses=clauses, joins=joins, values=values, opts=qopts)
    for (rpm_id,) in build_rpm_ids:
        query.values['rpm_id'] = rpm_id
        archive_ids = [i[0] for i in query.execute()]
        ret['component_of'].extend(archive_ids)

    if lazy and ret['component_of']:
        return ret

    # find archives whose buildroots we were in
    fields = ('id', 'type_id', 'type_name', 'build_id', 'filename')
    idx = {}
    q = """SELECT archiveinfo.id, archiveinfo.type_id, archivetypes.name, archiveinfo.build_id,
        archiveinfo.filename
    FROM buildroot_archives
        JOIN archiveinfo ON archiveinfo.buildroot_id = buildroot_archives.buildroot_id
        JOIN build ON archiveinfo.build_id = build.id
        JOIN archivetypes ON archivetypes.id = archiveinfo.type_id
    WHERE buildroot_archives.archive_id = %(archive_id)i
        AND build.state = %(st_complete)i"""
    if limit is not None:
        q += "\nLIMIT %(limit)i"
    for (archive_id,) in build_archive_ids:
        for row in _multiRow(q, locals(), fields):
            idx.setdefault(row['id'], row)
        if limit is not None and len(idx) > limit:
            break
    ret['archives'] = to_list(idx.values())

    if lazy and ret['archives']:
        return ret

    # find images/archives that contain the build archives
    fields = ['archive_id']
    joins = ['archiveinfo on archiveinfo.id = archive_id',
             'build on archiveinfo.build_id = build.id']
    clauses = ['archive_components.component_id = %(archive_id)s',
               'build.state = %(st_complete)s']
    values = {'st_complete': koji.BUILD_STATES['COMPLETE']}
    qopts = {'asList': True}
    if limit:
        qopts['limit'] = limit
    query = QueryProcessor(columns=fields, tables=['archive_components'],
                           clauses=clauses, joins=joins, values=values, opts=qopts)
    for (archive_id,) in build_archive_ids:
        query.values['archive_id'] = archive_id
        archive_ids = [i[0] for i in query.execute()]
        ret['component_of'].extend(archive_ids)

    if lazy and ret['component_of']:
        return ret

    # find timestamp of most recent use in a buildroot
    event_id = 0
    if build_rpm_ids:
        q = """SELECT MAX(create_event)
               FROM standard_buildroot
               WHERE buildroot_id IN (
                 SELECT buildroot_id
                 FROM buildroot_listing
                 WHERE rpm_id IN %(rpm_ids)s
               )"""
        event_id = (_fetchSingle(q, {'rpm_ids': build_rpm_ids}) or (0,))[0] or 0
    if build_archive_ids:
        q = """SELECT MAX(create_event)
               FROM standard_buildroot
               WHERE buildroot_id IN (
                 SELECT buildroot_id
                 FROM buildroot_archives
                 WHERE archive_id IN %(archive_ids)s
               )"""
        event_id2 = (_fetchSingle(q, {'archive_ids': build_archive_ids}) or (0,))[0] or 0
        event_id = max(event_id, event_id2)
    if event_id:
        q = """SELECT EXTRACT(EPOCH FROM get_event_time(%(event_id)i))"""
        ret['last_used'] = _singleValue(q, locals())
    else:
        ret['last_used'] = None

    # set 'images' field for backwards compat
    ret['images'] = ret['component_of']

    return ret


def delete_build(build, strict=True, min_ref_age=604800):
    """delete a build, if possible

    Attempts to delete a build. A build can only be deleted if it is
    unreferenced.

    If strict is true (default), an exception is raised if the build cannot
    be deleted.

    Note that a deleted build is not completely gone. It is marked deleted and some
    data remains in the database.  Mainly, the rpms are removed.

    Note in particular that deleting a build DOES NOT free any NVRs (or NVRAs) for
    reuse.

    Returns True if successful, False otherwise
    """
    context.session.assertPerm('admin')
    binfo = get_build(build, strict=True)
    refs = build_references(binfo['id'], limit=10, lazy=True)
    if refs.get('tags'):
        if strict:
            raise koji.GenericError("Cannot delete build, tagged: %s" % refs['tags'])
        return False
    if refs.get('rpms'):
        if strict:
            raise koji.GenericError("Cannot delete build, used in buildroots: %s" % refs['rpms'])
        return False
    if refs.get('archives'):
        if strict:
            raise koji.GenericError("Cannot delete build, used in archive buildroots: %s" %
                                    refs['archives'])
        return False
    if refs.get('component_of'):
        if strict:
            raise koji.GenericError("Cannot delete build, used as component of: %r" %
                                    refs['component_of'])
        return False
    if refs.get('last_used'):
        age = time.time() - refs['last_used']
        if age < min_ref_age:
            if strict:
                raise koji.GenericError("Cannot delete build, used in recent buildroot")
            return False
    # otherwise we can delete it
    _delete_build(binfo)
    return True


def _delete_build(binfo):
    """Delete a build (no reference checks)

    Please consider calling delete_build instead
    """
    # build-related data:
    #   build   KEEP (marked deleted)
    #   maven_builds KEEP
    #   win_builds KEEP
    #   image_builds KEEP
    #   build_types KEEP
    #   task ??
    #   tag_listing REVOKE (versioned) (but should ideally be empty anyway)
    #   rpminfo KEEP
    #           buildroot_listing KEEP (but should ideally be empty anyway)
    #           rpmsigs DELETE
    #   archiveinfo KEEP
    #               buildroot_archives KEEP (but should ideally be empty anyway)
    #   files on disk: DELETE
    st_deleted = koji.BUILD_STATES['DELETED']
    st_old = binfo['state']
    koji.plugin.run_callbacks('preBuildStateChange',
                              attribute='state', old=st_old, new=st_deleted, info=binfo)
    build_id = binfo['id']
    q = """SELECT id FROM rpminfo WHERE build_id=%(build_id)i"""
    rpm_ids = _fetchMulti(q, locals())
    for (rpm_id,) in rpm_ids:
        delete = """DELETE FROM rpmsigs WHERE rpm_id=%(rpm_id)i"""
        _dml(delete, locals())
    update = UpdateProcessor('tag_listing', clauses=["build_id=%(build_id)i"], values=locals())
    update.make_revoke()
    update.execute()
    update = """UPDATE build SET state=%(st_deleted)i WHERE id=%(build_id)i"""
    _dml(update, locals())
    # now clear the build dir
    builddir = koji.pathinfo.build(binfo)
    if os.path.exists(builddir):
        koji.util.rmtree(builddir)
    binfo = get_build(build_id, strict=True)
    koji.plugin.run_callbacks('postBuildStateChange',
                              attribute='state', old=st_old, new=st_deleted, info=binfo)


def reset_build(build):
    """Reset a build so that it can be reimported

    WARNING: this function is highly destructive. use with care.
    nulls task_id
    sets state to CANCELED
    clears all referenced data in other tables, including buildroot and
        archive component tables

    after reset, only the build table entry is left
    """
    # Only an admin may do this
    context.session.assertPerm('admin')
    binfo = get_build(build)
    if not binfo:
        # nothing to do
        return
    st_old = binfo['state']
    koji.plugin.run_callbacks('preBuildStateChange',
                              attribute='state', old=st_old, new=koji.BUILD_STATES['CANCELED'],
                              info=binfo)
    q = """SELECT id FROM rpminfo WHERE build_id=%(id)i"""
    ids = _fetchMulti(q, binfo)
    for (rpm_id,) in ids:
        delete = """DELETE FROM rpmsigs WHERE rpm_id=%(rpm_id)i"""
        _dml(delete, locals())
        delete = """DELETE FROM buildroot_listing WHERE rpm_id=%(rpm_id)i"""
        _dml(delete, locals())
        delete = """DELETE FROM archive_rpm_components WHERE rpm_id=%(rpm_id)i"""
        _dml(delete, locals())
    delete = """DELETE FROM rpminfo WHERE build_id=%(id)i"""
    _dml(delete, binfo)
    q = """SELECT id FROM archiveinfo WHERE build_id=%(id)i"""
    ids = _fetchMulti(q, binfo)
    for (archive_id,) in ids:
        delete = """DELETE FROM maven_archives WHERE archive_id=%(archive_id)i"""
        _dml(delete, locals())
        delete = """DELETE FROM win_archives WHERE archive_id=%(archive_id)i"""
        _dml(delete, locals())
        delete = """DELETE FROM image_archives WHERE archive_id=%(archive_id)i"""
        _dml(delete, locals())
        delete = """DELETE FROM buildroot_archives WHERE archive_id=%(archive_id)i"""
        _dml(delete, locals())
        delete = """DELETE FROM archive_rpm_components WHERE archive_id=%(archive_id)i"""
        _dml(delete, locals())
        delete = """DELETE FROM archive_components WHERE archive_id=%(archive_id)i"""
        _dml(delete, locals())
        delete = """DELETE FROM archive_components WHERE component_id=%(archive_id)i"""
        _dml(delete, locals())
    delete = """DELETE FROM archiveinfo WHERE build_id=%(id)i"""
    _dml(delete, binfo)
    delete = """DELETE FROM maven_builds WHERE build_id = %(id)i"""
    _dml(delete, binfo)
    delete = """DELETE FROM win_builds WHERE build_id = %(id)i"""
    _dml(delete, binfo)
    delete = """DELETE FROM image_builds WHERE build_id = %(id)i"""
    _dml(delete, binfo)
    delete = """DELETE FROM build_types WHERE build_id = %(id)i"""
    _dml(delete, binfo)
    delete = """DELETE FROM tag_listing WHERE build_id = %(id)i"""
    _dml(delete, binfo)
    binfo['state'] = koji.BUILD_STATES['CANCELED']
    update = """UPDATE build SET state=%(state)s, task_id=NULL, volume_id=0 WHERE id=%(id)s"""
    _dml(update, binfo)
    # now clear the build dir
    builddir = koji.pathinfo.build(binfo)
    if os.path.exists(builddir):
        koji.util.rmtree(builddir)
    binfo = get_build(build, strict=True)
    koji.plugin.run_callbacks('postBuildStateChange',
                              attribute='state', old=st_old, new=koji.BUILD_STATES['CANCELED'],
                              info=binfo)


def cancel_build(build_id, cancel_task=True):
    """Cancel a build

    Calling function should perform permission checks.

    If the build is associated with a task, cancel the task as well (unless
    cancel_task is False).
    Return True if the build was successfully canceled, False if not.

    The cancel_task option is used to prevent loops between task- and build-
    cancellation.
    """
    st_canceled = koji.BUILD_STATES['CANCELED']
    st_building = koji.BUILD_STATES['BUILDING']
    build = get_build(build_id, strict=True)
    if build['state'] != st_building:
        return False
    st_old = build['state']
    koji.plugin.run_callbacks('preBuildStateChange',
                              attribute='state', old=st_old, new=st_canceled, info=build)
    update = """UPDATE build
    SET state = %(st_canceled)i, completion_time = NOW()
    WHERE id = %(build_id)i AND state = %(st_building)i"""
    _dml(update, locals())
    build = get_build(build_id)
    if build['state'] != st_canceled:
        return False
    task_id = build['task_id']
    if task_id is not None:
        build_notification(task_id, build_id)
        if cancel_task:
            Task(task_id).cancelFull(strict=False)

    # remove possible CG reservations
    delete = "DELETE FROM build_reservations WHERE build_id = %(build_id)i"
    _dml(delete, {'build_id': build_id})

    build = get_build(build_id, strict=True)
    koji.plugin.run_callbacks('postBuildStateChange',
                              attribute='state', old=st_old, new=st_canceled, info=build)
    return True


def _get_build_target(task_id):
    # XXX Should we be storing a reference to the build target
    # in the build table for reproducibility?
    task = Task(task_id)
    info = task.getInfo(request=True)
    request = info['request']
    if info['method'] in ('build', 'maven'):
        # request is (source-url, build-target, map-of-other-options)
        if request[1]:
            return get_build_target(request[1])
    elif info['method'] == 'winbuild':
        # request is (vm-name, source-url, build-target, map-of-other-options)
        if request[2]:
            return get_build_target(request[2])
    return None


def get_notification_recipients(build, tag_id, state):
    """
    Return the list of email addresses that should be notified about events
    involving the given build and tag.  This could be the build into that tag
    succeeding or failing, or the build being manually tagged or untagged from
    that tag.

    The list will contain email addresss for all users who have registered for
    notifications on the package or tag (or both), as well as the package owner
    for this tag and the user who submitted the build.  The list will not contain
    duplicates.

    Only active 'human' users will be in this list.
    """

    joins = ['JOIN users ON build_notifications.user_id = users.id']
    users_status = koji.USER_STATUS['NORMAL']
    users_usertypes = [koji.USERTYPES['NORMAL'], koji.USERTYPES['GROUP']]
    clauses = [
        'status = %(users_status)i',
        'usertype IN %(users_usertypes)s',
    ]

    if not build and tag_id:
        raise koji.GenericError('Invalid call')

    if build:
        package_id = build['package_id']
        clauses.append('package_id = %(package_id)i OR package_id IS NULL')
    else:
        clauses.append('package_id IS NULL')
    if tag_id:
        clauses.append('tag_id = %(tag_id)i OR tag_id IS NULL')
    else:
        clauses.append('tag_id IS NULL')
    if state != koji.BUILD_STATES['COMPLETE']:
        clauses.append('success_only = FALSE')

    query = QueryProcessor(columns=('user_id', 'email'), tables=['build_notifications'],
                           joins=joins, clauses=clauses, values=locals())
    recipients = query.execute()

    email_domain = context.opts['EmailDomain']
    notify_on_success = context.opts['NotifyOnSuccess']

    if build and (notify_on_success is True or state != koji.BUILD_STATES['COMPLETE']):
        # user who submitted the build
        recipients.append({
            'user_id': build['owner_id'],
            'email': '%s@%s' % (build['owner_name'], email_domain)
        })

        if tag_id:
            packages = readPackageList(pkgID=package_id, tagID=tag_id, inherit=True)
            # owner of the package in this tag, following inheritance
            pkgdata = packages.get(package_id)
            # If the package list has changed very recently it is possible we
            # will get no result.
            if pkgdata and not pkgdata['blocked']:
                owner = get_user(pkgdata['owner_id'], strict=True)
                if owner['status'] == koji.USER_STATUS['NORMAL'] and \
                   owner['usertype'] == koji.USERTYPES['NORMAL']:
                    recipients.append({
                        'user_id': owner['id'],
                        'email': '%s@%s' % (owner['name'], email_domain)
                    })
        # FIXME - if tag_id is None, we don't have a good way to get the package owner.
        #   using all package owners from all tags would be way overkill.

    if not recipients:
        return []

    # apply the opt-outs
    user_ids = list(set([r['user_id'] for r in recipients]))
    if user_ids:
        clauses = ['user_id IN %(user_ids)s']
        if build:
            package_id = build['package_id']
            clauses.append('package_id = %(package_id)i OR package_id IS NULL')
        else:
            clauses.append('package_id IS NULL')
        if tag_id:
            clauses.append('tag_id = %(tag_id)i OR tag_id IS NULL')
        else:
            clauses.append('tag_id IS NULL')
        query = QueryProcessor(columns=['user_id'], clauses=clauses,
                               tables=['build_notifications_block'], values=locals())
        optouts = [r['user_id'] for r in query.execute()]
        optouts = set(optouts)
    else:
        optouts = set()

    emails = [r['email'] for r in recipients if r['user_id'] not in optouts]
    return list(set(emails))


def tag_notification(is_successful, tag_id, from_id, build_id, user_id, ignore_success=False,
                     failure_msg=''):
    if context.opts.get('DisableNotifications'):
        return
    if is_successful:
        state = koji.BUILD_STATES['COMPLETE']
    else:
        state = koji.BUILD_STATES['FAILED']
    recipients = {}
    build = get_build(build_id)
    if not build:
        # the build doesn't exist, so there's nothing to send a notification about
        return None
    if tag_id:
        tag = get_tag(tag_id)
        if tag:
            for email in get_notification_recipients(build, tag['id'], state):
                recipients[email] = 1
    if from_id:
        from_tag = get_tag(from_id)
        if from_tag:
            for email in get_notification_recipients(build, from_tag['id'], state):
                recipients[email] = 1
    recipients_uniq = to_list(recipients.keys())
    if len(recipients_uniq) > 0 and not (is_successful and ignore_success):
        task_id = make_task('tagNotification',
                            [recipients_uniq, is_successful, tag_id, from_id, build_id, user_id,
                             ignore_success, failure_msg])
        return task_id
    return None


def build_notification(task_id, build_id):
    if context.opts.get('DisableNotifications'):
        return
    build = get_build(build_id)
    target = _get_build_target(task_id)

    dest_tag = None
    if target:
        dest_tag = target['dest_tag']

    if build['state'] == koji.BUILD_STATES['BUILDING']:
        raise koji.GenericError('never send notifications for incomplete builds')

    web_url = context.opts.get('KojiWebURL', 'http://localhost/koji')

    recipients = get_notification_recipients(build, dest_tag, build['state'])
    if recipients:
        make_task('buildNotification', [recipients, build, target, web_url])


def get_build_notifications(user_id):
    query = QueryProcessor(tables=['build_notifications'],
                           columns=('id', 'user_id', 'package_id', 'tag_id',
                                    'success_only', 'email'),
                           clauses=['user_id = %(user_id)i'],
                           values=locals())
    return query.execute()


def get_build_notification_blocks(user_id):
    query = QueryProcessor(tables=['build_notifications_block'],
                           columns=['id', 'user_id', 'package_id', 'tag_id'],
                           clauses=['user_id = %(user_id)i'],
                           values=locals())
    return query.execute()


def new_group(name):
    """Add a user group to the database"""
    context.session.assertPerm('admin')
    if get_user(name):
        raise koji.GenericError('user/group already exists: %s' % name)
    return context.session.createUser(name, usertype=koji.USERTYPES['GROUP'])


def add_group_member(group, user, strict=True):
    """Add user to group"""
    context.session.assertPerm('admin')
    ginfo = get_user(group)
    uinfo = get_user(user)
    if not ginfo or ginfo['usertype'] != koji.USERTYPES['GROUP']:
        raise koji.GenericError("Not a group: %s" % group)
    if not uinfo:
        raise koji.GenericError("Not an user: %s" % user)
    if uinfo['usertype'] == koji.USERTYPES['GROUP']:
        raise koji.GenericError("Groups cannot be members of other groups")
    # check to see if user is already a member
    data = {'user_id': uinfo['id'], 'group_id': ginfo['id']}
    table = 'user_groups'
    clauses = ('user_id = %(user_id)i', 'group_id = %(group_id)s')
    query = QueryProcessor(columns=['user_id'], tables=[table],
                           clauses=('active = TRUE',) + clauses,
                           values=data, opts={'rowlock': True})
    row = query.executeOne()
    if row:
        if not strict:
            return
        raise koji.GenericError("User already in group")
    insert = InsertProcessor(table, data)
    insert.make_create()
    insert.execute()


def drop_group_member(group, user):
    """Drop user from group"""
    context.session.assertPerm('admin')
    user = get_user(user, strict=True)
    ginfo = get_user(group)
    if not ginfo or ginfo['usertype'] != koji.USERTYPES['GROUP']:
        raise koji.GenericError("No such group: %s" % group)
    if user['id'] not in [u['id'] for u in get_group_members(group)]:
        raise koji.GenericError("No such user in group: %s" % group)
    data = {'user_id': user['id'], 'group_id': ginfo['id']}
    clauses = ["user_id = %(user_id)i", "group_id = %(group_id)i"]
    update = UpdateProcessor('user_groups', values=data, clauses=clauses)
    update.make_revoke()
    update.execute()


def get_group_members(group):
    """Get the members of a group"""
    context.session.assertPerm('admin')
    ginfo = get_user(group)
    if not ginfo or ginfo['usertype'] != koji.USERTYPES['GROUP']:
        raise koji.GenericError("Not a group: %s" % group)
    group_id = ginfo['id']
    columns = ('id', 'name', 'usertype', 'array_agg(krb_principal)')
    aliases = ('id', 'name', 'usertype', 'krb_principals')
    joins = ['JOIN users ON user_groups.user_id = users.id',
             'LEFT JOIN user_krb_principals'
             ' ON users.id = user_krb_principals.user_id']
    clauses = [eventCondition(None), 'group_id = %(group_id)i']

    query = QueryProcessor(tables=['user_groups'],
                           columns=columns,
                           aliases=aliases,
                           joins=joins,
                           clauses=clauses,
                           values=locals(),
                           opts={'group': 'users.id'},
                           enable_group=True,
                           transform=xform_user_krb)
    return query.iterate()


def set_user_status(user, status):
    context.session.assertPerm('admin')
    if not koji.USER_STATUS.get(status):
        raise koji.GenericError('invalid status: %s' % status)
    if user['status'] == status:
        # nothing to do
        return
    update = """UPDATE users SET status = %(status)i WHERE id = %(user_id)i"""
    user_id = user['id']
    rows = _dml(update, locals())
    # sanity check
    if rows == 0:
        raise koji.GenericError('invalid user ID: %i' % user_id)


def list_cgs():
    """List all available content generators in the system

    :returns: A map of content generators, like {"name": data}. The data map
              for each content generator has an "id" key for the content
              generator ID, and a "users" key for the a list usernames who
              are permitted to import for this content generator.
    """

    fields = {'content_generator.id': 'id', 'content_generator.name': 'name',
              'users.name': 'user_name'}
    columns, aliases = zip(*fields.items())
    tables = ['cg_users']
    joins = ['content_generator ON content_generator.id = cg_users.cg_id',
             'users ON users.id = cg_users.user_id']
    clauses = ['cg_users.active = TRUE']
    query = QueryProcessor(tables=tables, aliases=aliases, columns=columns,
                           joins=joins, clauses=clauses)
    cgs = {}
    for result in query.iterate():
        cg_id = result['id']
        cg_name = result['name']
        user_name = result['user_name']
        if cg_name not in cgs:
            cgs[cg_name] = {'id': cg_id, 'users': []}
        cgs[cg_name]['users'].append(user_name)
    return cgs


def grant_cg_access(user, cg, create=False):
    """
    Grant user access to act as the given content generator

    :param user: koji userid or username
    :type user: int or str
    :param cg: content generator id or name
    :type cg: int or str
    :param bool create: If True, and the requested cg name entry does not
                        already exist, then Koji will create the content
                        generator entry. In such a case, the cg parameter
                        must be a string. The default is False.
    """

    context.session.assertPerm('admin')
    user = get_user(user, strict=True)
    if create:
        cg = lookup_name('content_generator', cg, create=True)
    else:
        cg = lookup_name('content_generator', cg, strict=True)
    ins = InsertProcessor('cg_users')
    ins.set(cg_id=cg['id'], user_id=user['id'])
    ins.make_create()
    if ins.dup_check():
        raise koji.GenericError("User already has access to content generator %(name)s" % cg)
    ins.execute()


def revoke_cg_access(user, cg):
    """
    Revoke a user's access to act as the given content generator

    :param user: koji userid or username
    :type user: int or str
    :param cg: content generator id or name
    :type cg: int or str
    """

    context.session.assertPerm('admin')
    user = get_user(user, strict=True)
    cg = lookup_name('content_generator', cg, strict=True)
    data = {'user_id': user['id'], 'cg_id': cg['id']}
    update = UpdateProcessor('cg_users', values=data,
                             clauses=["user_id = %(user_id)i", "cg_id = %(cg_id)i"])
    update.make_revoke()
    update.execute()


def assert_cg(cg, user=None):
    cg = lookup_name('content_generator', cg, strict=True)
    if user is None:
        if not context.session.logged_in:
            raise koji.AuthError("Not logged in")
        user = context.session.user_id
    user = get_user(user, strict=True)
    clauses = ['active = TRUE', 'user_id = %(user_id)s', 'cg_id = %(cg_id)s']
    data = {'user_id': user['id'], 'cg_id': cg['id']}
    query = QueryProcessor(tables=['cg_users'], columns=['cg_id'], clauses=clauses, values=data)
    if not query.execute():
        raise koji.AuthError("Content generator access required (%s)" % cg['name'])


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


def parse_json(value, desc=None, errstr=None):
    if value is None:
        return value
    try:
        return koji.fixEncodingRecurse(json.loads(value))
    except Exception:
        if errstr is None:
            if desc is None:
                errstr = "Invalid json data for %s" % desc
            else:
                errstr = "Invalid json data"
        raise koji.GenericError("%s: %r" % (errstr, value))


def _fix_extra_field(row):
    row['extra'] = parse_json(row['extra'], errstr='Invalid extra data')
    return row


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
        columns = sorted(to_list(self.data.keys()) + to_list(self.rawdata.keys()))
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
        query = QueryProcessor(columns=to_list(data.keys()), tables=[self.table],
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
                    raise Exception('invalid order: ' + order)
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
            logger.debug('Setting up query iterator. cname=%r', cname)
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

#
# Policy Test Handlers


class OperationTest(koji.policy.MatchTest):
    """Checks operation against glob patterns"""
    name = 'operation'
    field = 'operation'


def policy_get_user(data):
    """Determine user from policy data (default to logged-in user)"""
    if 'user_id' in data:
        return get_user(data['user_id'])
    elif context.session.logged_in:
        return get_user(context.session.user_id)
    return None


def policy_get_pkg(data):
    """Determine package from policy data (default to logged-in user)

    returns dict as lookup_package
    if package does not exist yet, the id field will be None
    """
    if 'package' in data:
        pkginfo = lookup_package(data['package'], strict=False)
        if not pkginfo:
            # for some operations (e.g. adding a new package), the package
            # entry may not exist yet
            if isinstance(data['package'], str):
                return {'id': None, 'name': data['package']}
            else:
                raise koji.GenericError("Invalid package: %s" % data['package'])
        return pkginfo
    if 'build' in data:
        binfo = get_build(data['build'], strict=True)
        return {'id': binfo['package_id'], 'name': binfo['name']}
    # else
    raise koji.GenericError("policy requires package data")


def policy_get_version(data):
    """Determine version from policy data

    returns version as string
    """
    if 'version' in data:
        return data['version']
    if 'build' in data:
        return get_build(data['build'], strict=True)['version']
    # else
    raise koji.GenericError("policy requires version data")


def policy_get_release(data):
    """Determine release from policy data

    returns release as string
    """
    if 'release' in data:
        return data['release']
    if 'build' in data:
        return get_build(data['build'], strict=True)['release']
    # else
    raise koji.GenericError("policy requires release data")


def policy_get_brs(data):
    """Determine content generators from policy data"""

    if 'buildroots' in data:
        return set(data['buildroots'])
    elif 'build' in data:
        binfo = get_build(data['build'], strict=True)
        rpm_brs = [r['buildroot_id'] for r in list_rpms(buildID=binfo['id'])]
        archive_brs = [a['buildroot_id'] for a in list_archives(buildID=binfo['id'])]
        return set(rpm_brs + archive_brs)
    else:
        return set()


def policy_get_cgs(data):
    # pull cg info out
    # note that br_id will be None if a component had no buildroot
    if 'cg_list' in data:
        cgs = [lookup_name('content_generator', cg, strict=True)
               for cg in data['cg_list']]
        return set(cgs)
    # otherwise try buildroot data
    cgs = set()
    for br_id in policy_get_brs(data):
        if br_id is None:
            cgs.add(None)
        else:
            cgs.add(get_buildroot(br_id, strict=True)['cg_name'])
    return cgs


def policy_get_build_tags(data):
    if 'build_tag' in data:
        return [get_tag(data['build_tag'], strict=True)['name']]
    elif 'build_tags' in data:
        return [get_tag(t, strict=True)['name'] for t in data['build_tags']]

    # see if we have a target
    target = data.get('target')
    if target:
        target = get_build_target(target, strict=False)
        if target:
            return [target['build_tag_name']]

    # otherwise look at buildroots
    tags = set()
    for br_id in policy_get_brs(data):
        if br_id is None:
            tags.add(None)
        else:
            tags.add(get_buildroot(br_id, strict=True)['tag_name'])
    return tags


def policy_get_build_types(data):
    if 'btypes' in data:
        # btypes can be already populated by caller
        return set(data['btypes'])
    if 'build' in data:
        binfo = get_build(data['build'], strict=True)
        return set(get_build_type(binfo).keys())
    return set()


class NewPackageTest(koji.policy.BaseSimpleTest):
    """Checks to see if a package exists yet"""
    name = 'is_new_package'

    def run(self, data):
        return (policy_get_pkg(data)['id'] is None)


class PackageTest(koji.policy.MatchTest):
    """Checks package against glob patterns"""
    name = 'package'
    field = '_package'

    def run(self, data):
        # we need to find the package name from the base data
        data[self.field] = policy_get_pkg(data)['name']
        return super(PackageTest, self).run(data)


class VersionTest(koji.policy.MatchTest):
    """Checks version against glob patterns"""
    name = 'version'
    field = '_version'

    def run(self, data):
        data[self.field] = policy_get_version(data)
        return super(VersionTest, self).run(data)


class ReleaseTest(koji.policy.MatchTest):
    """Checks release against glob patterns"""
    name = 'release'
    field = '_release'

    def run(self, data):
        # we need to find the build NVR from the base data
        data[self.field] = policy_get_release(data)
        return super(ReleaseTest, self).run(data)


class VolumeTest(koji.policy.MatchTest):
    """Checks storage volume against glob patterns"""
    name = 'volume'
    field = '_volume'

    def run(self, data):
        # we need to find the volume name from the base data
        volinfo = None
        if 'volume' in data:
            volinfo = lookup_name('volume', data['volume'], strict=False)
        elif 'build' in data:
            build = get_build(data['build'])
            volinfo = {'id': build['volume_id'], 'name': build['volume_name']}
        if not volinfo:
            return False
        data[self.field] = volinfo['name']
        return super(VolumeTest, self).run(data)


class CGMatchAnyTest(koji.policy.BaseSimpleTest):
    """Checks content generator against glob patterns

    The 'any' means that if any of the cgs for the build (there can be more
    than one) match the pattern list, then the result is True
    """

    name = 'cg_match_any'

    def run(self, data):
        # we need to find the volume name from the base data
        cgs = policy_get_cgs(data)
        patterns = self.str.split()[1:]
        for cg_name in cgs:
            if cg_name is None:
                # component with no br, or br with no cg
                continue
            if multi_fnmatch(cg_name, patterns):
                return True
        # else
        return False


class CGMatchAllTest(koji.policy.BaseSimpleTest):
    """Checks content generator against glob patterns

    The 'all' means that all of the cgs for the build (there can be more
    than one) must match the pattern list for the result to be true.
    """

    name = 'cg_match_all'

    def run(self, data):
        # we need to find the volume name from the base data
        cgs = policy_get_cgs(data)
        if not cgs:
            return False
        patterns = self.str.split()[1:]
        for cg_name in cgs:
            if cg_name is None:
                return False
            if not multi_fnmatch(cg_name, patterns):
                return False
        # else
        return True


class TagTest(koji.policy.MatchTest):
    name = 'tag'
    field = '_tagname'

    def get_tag(self, data):
        """extract the tag to test against from the data

        return None if there is no tag to test
        """
        tag = data.get('tag')
        if tag is None:
            return None
        return get_tag(tag, strict=False)

    def run(self, data):
        # we need to find the tag name from the base data
        tinfo = self.get_tag(data)
        if tinfo is None:
            return False
        data[self.field] = tinfo['name']
        return super(TagTest, self).run(data)


class FromTagTest(TagTest):
    name = 'fromtag'

    def get_tag(self, data):
        tag = data.get('fromtag')
        if tag is None:
            return None
        return get_tag(tag, strict=False)


class HasTagTest(koji.policy.BaseSimpleTest):
    """Check to see if build (currently) has a given tag"""
    name = 'hastag'

    def run(self, data):
        if 'build' not in data:
            return False
        tags = list_tags(build=data['build'])
        # True if any of these tags match any of the patterns
        args = self.str.split()[1:]
        for tag in tags:
            for pattern in args:
                if fnmatch.fnmatch(tag['name'], pattern):
                    return True
        # otherwise...
        return False


class SkipTagTest(koji.policy.BaseSimpleTest):
    """Check for the skip_tag option

    For policies regarding build tasks (e.g. build_from_srpm)
    """
    name = 'skip_tag'

    def run(self, data):
        return bool(data.get('skip_tag'))


class BuildTagTest(koji.policy.BaseSimpleTest):
    """Check the build tag(s) of the build

    If build_tag is not provided in policy data, it is determined by the
    buildroots of the component rpms
    """
    name = 'buildtag'

    def run(self, data):
        args = self.str.split()[1:]
        for tagname in policy_get_build_tags(data):
            if tagname is None:
                # content generator buildroots might not have tag info
                continue
            if multi_fnmatch(tagname, args):
                return True
        # otherwise...
        return False


class BuildTypeTest(koji.policy.BaseSimpleTest):
    """Check the build type(s) of the build"""

    name = 'buildtype'

    def run(self, data):
        args = self.str.split()[1:]
        for btype in policy_get_build_types(data):
            if multi_fnmatch(btype, args):
                return True
        return False


class ImportedTest(koji.policy.BaseSimpleTest):
    """Check if any part of a build was imported

    This is determined by checking the buildroots of the rpms and archives
    True if any of them lack a buildroot (strict)"""
    name = 'imported'

    def run(self, data):
        build_info = data.get('build')
        if not build_info:
            raise koji.GenericError('policy data must contain a build')
        build_id = get_build(build_info, strict=True)['id']
        # no test args
        for rpminfo in list_rpms(buildID=build_id):
            if rpminfo['buildroot_id'] is None:
                return True
        for archive in list_archives(buildID=build_id):
            if archive['buildroot_id'] is None:
                return True
        # otherwise...
        return False


class ChildTaskTest(koji.policy.BoolTest):
    name = 'is_child_task'
    field = 'parent'


class MethodTest(koji.policy.MatchTest):
    name = 'method'
    field = 'method'


class UserTest(koji.policy.MatchTest):
    """Checks username against glob patterns"""
    name = 'user'
    field = '_username'

    def run(self, data):
        user = policy_get_user(data)
        if not user:
            return False
        data[self.field] = user['name']
        return super(UserTest, self).run(data)


class VMTest(koji.policy.MatchTest):
    """Checks a VM name against glob patterns"""
    name = 'vm_name'
    field = 'vm_name'


class IsBuildOwnerTest(koji.policy.BaseSimpleTest):
    """Check if user owns the build"""
    name = "is_build_owner"

    def run(self, data):
        build = get_build(data['build'])
        owner = get_user(build['owner_id'])
        user = policy_get_user(data)
        if not user:
            return False
        if owner['id'] == user['id']:
            return True
        if owner['usertype'] == koji.USERTYPES['GROUP']:
            # owner is a group, check to see if user is a member
            if owner['id'] in koji.auth.get_user_groups(user['id']):
                return True
        # otherwise...
        return False


class UserInGroupTest(koji.policy.BaseSimpleTest):
    """Check if user is in group(s)

    args are treated as patterns and matched against group name
    true if user is in /any/ matching group
    """
    name = "user_in_group"

    def run(self, data):
        user = policy_get_user(data)
        if not user:
            return False
        groups = koji.auth.get_user_groups(user['id'])
        args = self.str.split()[1:]
        for group_id, group in groups.items():
            for pattern in args:
                if fnmatch.fnmatch(group, pattern):
                    return True
        # otherwise...
        return False


class HasPermTest(koji.policy.BaseSimpleTest):
    """Check if user has permission(s)

    args are treated as patterns and matched against permission name
    true if user has /any/ matching permission
    """
    name = "has_perm"

    def run(self, data):
        user = policy_get_user(data)
        if not user:
            return False
        perms = koji.auth.get_user_perms(user['id'])
        args = self.str.split()[1:]
        for perm in perms:
            for pattern in args:
                if fnmatch.fnmatch(perm, pattern):
                    return True
        # otherwise...
        return False


class SourceTest(koji.policy.MatchTest):
    """Match build source

    This is not the cleanest, since we have to crack open the task parameters
    True if build source matches any of the supplied patterns
    """
    name = "source"
    field = '_source'

    def run(self, data):
        if 'source' in data:
            data[self.field] = data['source']
        elif 'build' in data:
            build = get_build(data['build'])
            if build['source'] is not None:
                data[self.field] = build['source']
            elif build['task_id'] is None:
                # no source to match against
                return False
            else:
                # crack open the build task
                task = Task(build['task_id'])
                info = task.getInfo()
                params = task.getRequest()
                # signatures:
                # build - (src, target, opts=None)
                # maven - (url, target, opts=None)
                # winbuild - (name, source_url, target, opts=None)
                if info['method'] == 'winbuild':
                    data[self.field] = params[1]
                elif info['method'] == 'indirectionimage':
                    return False
                else:
                    data[self.field] = params[0]
        else:
            return False
        return super(SourceTest, self).run(data)


class PolicyTest(koji.policy.BaseSimpleTest):
    """Test named policy

    The named policy must exist
    Returns True is the policy results in an action of:
        yes, true, allow
    Otherwise returns False
    (Also returns False if there are no matches in the policy)
    Watch out for loops
    """
    name = 'policy'

    def __init__(self, str):
        super(PolicyTest, self).__init__(str)
        self.depth = 0
        # this is used to detect loops. Note that each test in a ruleset is
        # a distinct instance of its test class. So this value is particular
        # to a given appearance of a policy check in a ruleset.

    def run(self, data):
        args = self.str.split()[1:]
        if self.depth != 0:
            # LOOP!
            raise koji.GenericError("encountered policy loop at %s" % self.str)
        ruleset = context.policy.get(args[0])
        if not ruleset:
            raise koji.GenericError("no such policy: %s" % args[0])
        self.depth += 1
        result = ruleset.apply(data)
        self.depth -= 1
        if result is None:
            return False
        else:
            return result.lower() in ('yes', 'true', 'allow')


def check_policy(name, data, default='deny', strict=False, force=False):
    """Check data against the named policy

    This assumes the policy actions consist of:
        allow
        deny

    Returns a pair (access, reason)
        access: True if the policy result is allow, false otherwise
        reason: reason for the access
    If strict is True, will raise ActionNotAllowed if the action is not 'allow'
    If force is True, policy will pass (under admin), but action will be logged
    """
    ruleset = context.policy.get(name)
    if not ruleset:
        if context.opts.get('MissingPolicyOk'):
            # for backwards compatibility, this is the default
            result = "allow"
        else:
            result = "deny"
        reason = "missing policy"
        lastrule = ''
    else:
        result = ruleset.apply(data)
        if result is None:
            result = default
            reason = 'not covered by policy'
        else:
            parts = result.split(None, 1)
            parts.extend(['', ''])
            result, reason = parts[:2]
            reason = reason.lower()
        lastrule = ruleset.last_rule()
    if context.opts.get('KojiDebug', False):
        logger.error(
            "policy %(name)s gave %(result)s, reason: %(reason)s, last rule: %(lastrule)s",
            locals())
    if result == 'allow':
        return True, reason
    if result != 'deny':
        reason = 'error in policy'
        logger.error("Invalid action in policy %s, rule: %s", name, lastrule)
    if force:
        user = policy_get_user(data)
        if user and 'admin' in koji.auth.get_user_perms(user['id']):
            msg = "Policy %s overriden by force: %s" % (name, user["name"])
            if reason:
                msg += ": %s" % reason
            logger.info(msg)
            return True, "overriden by force"
    if not strict:
        return False, reason
    err_str = "policy violation (%s)" % name
    if reason:
        err_str += ": %s" % reason
    if context.opts.get('KojiDebug') or context.opts.get('VerbosePolicy'):
        err_str += " [rule: %s]" % lastrule
    raise koji.ActionNotAllowed(err_str)


def policy_data_from_task(task_id):
    """Calculate policy data from task id

        :param int task_id: the task id

        :returns: dict with policy data
        """
    task = Task(task_id)
    taskinfo = task.getInfo(strict=True, request=True)
    return policy_data_from_task_args(taskinfo['method'], taskinfo['request'])


def policy_data_from_task_args(method, arglist):
    """Calculate policy data from task arguments

        :param str method: task method
        :param list arglist: raw task params

        :returns: dict with policy data
        """
    params = {}
    policy_data = {}
    try:
        params = koji.tasks.parse_task_params(method, arglist)
    except TypeError:
        logger.warning("%s is not a standard koji task", method)
    except koji.ParameterError:
        logger.warning("Cannot parse parameters: %s of %s task", arglist, method)
    except Exception:
        logger.warning("Unexcepted error occurs when parsing parameters: %s of %s task",
                       arglist, method, exc_info=True)
    if not params:
        return {}

    if method == 'indirectionimage':
        # this handler buries all its arguments in a single 'opts' parameter
        opts = params.get('opts') or {}
        params = dict(**opts)
        params['opts'] = opts
    # parameters that indicate source for build
    for k in ('src', 'spec_url', 'url'):
        if method == 'newRepo':
            # newRepo has a 'src' parameter that means something else
            break
        if k in params:
            policy_data['source'] = params.get(k)
            break
    # parameters that indicate build target
    target = None
    hastarget = False
    for k in ('target', 'build_target', 'target_info'):
        if k in params:
            target = params.get(k)
            hastarget = True
            break
    if hastarget:
        if isinstance(target, dict):
            if 'name' not in target:
                logger.warning("Bad build target parameter: %r", target)
                target = None
            else:
                target = target.get('name')
        if target is None:
            policy_data['target'] = None
        else:
            policy_data['target'] = get_build_target(target, strict=True)['name']
    t_opts = params.get('opts', {})
    policy_data['scratch'] = t_opts.get('scratch', False)

    return policy_data


def assert_policy(name, data, default='deny', force=False):
    """Enforce the named policy

    This assumes the policy actions consist of:
        allow
        deny
    Raises ActionNotAllowed if policy result is not allow
    """
    check_policy(name, data, default=default, strict=True, force=force)


def rpmdiff(basepath, rpmlist, hashes):
    "Diff the first rpm in the list against the rest of the rpms."
    if len(rpmlist) < 2:
        return
    first_rpm = rpmlist[0]
    task_id = first_rpm.split('/')[1]
    first_hash = hashes.get(task_id, {}).get(os.path.basename(first_rpm), False)
    for other_rpm in rpmlist[1:]:
        if first_hash:
            task_id = other_rpm.split('/')[1]
            other_hash = hashes[task_id][os.path.basename(other_rpm)]
            if first_hash == other_hash:
                logger.debug("Skipping noarch rpmdiff for %s vs %s" % (first_rpm, other_rpm))
                continue
        # ignore differences in file size, md5sum, and mtime
        # (files may have been generated at build time and contain
        #  embedded dates or other insignificant differences)
        d = koji.rpmdiff.Rpmdiff(joinpath(basepath, first_rpm),
                                 joinpath(basepath, other_rpm), ignore='S5TN')
        if d.differs():
            raise koji.BuildError(
                'The following noarch package built differently on different architectures: %s\n'
                'rpmdiff output was:\n%s' % (os.path.basename(first_rpm), d.textdiff()))


def importImageInternal(task_id, build_info, imgdata):
    """
    Import image info and the listing into the database, and move an image
    to the final resting place. The filesize may be reported as a string if it
    exceeds the 32-bit signed integer limit. This function will convert it if
    need be. This is the completeBuild for images; it should not be called for
    scratch images.

    imgdata is:
    arch - the arch if the image
    task_id - the task that created the image
    files - files associated with the image (appliances have multiple files)
    rpmlist - the list of RPM NVRs installed into the image
    """
    host = Host()
    host.verify()
    task = Task(task_id)
    task.assertHost(host.id)
    tinfo = task.getInfo()

    koji.plugin.run_callbacks('preImport', type='image', image=imgdata)

    # import the build output
    workpath = koji.pathinfo.task(imgdata['task_id'])
    imgdata['relpath'] = koji.pathinfo.taskrelpath(imgdata['task_id'])
    archives = []
    for imgfile in imgdata['files']:
        fullpath = joinpath(workpath, imgfile)
        archivetype = get_archive_type(imgfile)
        logger.debug('image type we are importing is: %s' % archivetype)
        if not archivetype:
            raise koji.BuildError('Unsupported image type')
        archives.append(import_archive(fullpath, build_info, 'image', imgdata))

    # upload logs
    logs = [f for f in os.listdir(workpath) if f.endswith('.log')]
    for logfile in logs:
        logsrc = joinpath(workpath, logfile)
        if tinfo['method'] == 'livemedia':
            # multiarch livemedia spins can have log name conflicts, so we
            # add the arch to the path
            logdir = joinpath(koji.pathinfo.build(build_info),
                              'data/logs/image', imgdata['arch'])
        else:
            logdir = joinpath(koji.pathinfo.build(build_info),
                              'data/logs/image')
        koji.ensuredir(logdir)
        final_path = joinpath(logdir, os.path.basename(logfile))
        if os.path.exists(final_path):
            raise koji.GenericError("Error importing build log. %s already exists." % final_path)
        if os.path.islink(logsrc) or not os.path.isfile(logsrc):
            raise koji.GenericError("Error importing build log. %s is not a regular file." %
                                    logsrc)
        move_and_symlink(logsrc, final_path, create_dir=True)

    # record all of the RPMs installed in the image(s)
    # verify they were built in Koji or in an external repo
    rpm_ids = []
    for an_rpm in imgdata['rpmlist']:
        location = an_rpm.get('location')
        if location:
            data = add_external_rpm(an_rpm, location, strict=False)
        else:
            data = get_rpm(an_rpm, strict=True)
        rpm_ids.append(data['id'])

    # associate those RPMs with the image
    insert = BulkInsertProcessor('archive_rpm_components')
    for archive in archives:
        logger.info('working on archive %s', archive)
        if archive['filename'].endswith('xml'):
            continue
        logger.info('associating installed rpms with %s', archive['id'])
        for rpm_id in rpm_ids:
            insert.add_record(archive_id=archive['id'], rpm_id=rpm_id)
    if insert.data:
        insert.execute()

    koji.plugin.run_callbacks('postImport', type='image', image=imgdata,
                              build=build_info, fullpath=fullpath)

#
# XMLRPC Methods
#


class RootExports(object):
    '''Contains functions that are made available via XMLRPC'''

    def restartHosts(self, priority=5, options=None):
        """Spawns restartHosts task

        :param int priority: task priority
        :param dict options: additional task arguments (see restartHosts task)

        :returns: task ID
        """
        context.session.assertPerm('host')
        if options is None:
            args = []
        else:
            args = [options]
        return make_task('restartHosts', args, priority=priority)

    def build(self, src, target, opts=None, priority=None, channel=None):
        """Create a build task

        priority: the amount to increase (or decrease) the task priority, relative
                  to the default priority; higher values mean lower priority; only
                  admins have the right to specify a negative priority here
        channel: the channel to allocate the task to
        Returns the task id
        """
        context.session.assertLogin()
        if not opts:
            opts = {}
        taskOpts = {}
        if priority:
            if priority < 0:
                if not context.session.hasPerm('admin'):
                    raise koji.ActionNotAllowed('only admins may create high-priority tasks')
            taskOpts['priority'] = koji.PRIO_DEFAULT + priority
        if channel:
            taskOpts['channel'] = channel
        return make_task('build', [src, target, opts], **taskOpts)

    def chainBuild(self, srcs, target, opts=None, priority=None, channel=None):
        """Create a chained build task for building sets of packages in order

        srcs: list of pkg lists, ie [[src00, src01, src03],[src20],[src30,src31],...]
              where each of the top-level lists gets built and a new repo is created
              before the next list is built.
        target: build target
        priority: the amount to increase (or decrease) the task priority, relative
                  to the default priority; higher values mean lower priority; only
                  admins have the right to specify a negative priority here
        channel: the channel to allocate the task to
        Returns a list of all the dependent task ids
        """
        context.session.assertLogin()
        if not opts:
            opts = {}
        taskOpts = {}
        if priority:
            if priority < 0:
                if not context.session.hasPerm('admin'):
                    raise koji.ActionNotAllowed('only admins may create high-priority tasks')
            taskOpts['priority'] = koji.PRIO_DEFAULT + priority
        if channel:
            taskOpts['channel'] = channel

        return make_task('chainbuild', [srcs, target, opts], **taskOpts)

    def mavenBuild(self, url, target, opts=None, priority=None, channel='maven'):
        """Create a Maven build task

        url: The url to checkout the source from.  May be a CVS, SVN, or GIT repository.
        target: the build target
        priority: the amount to increase (or decrease) the task priority, relative
                  to the default priority; higher values mean lower priority; only
                  admins have the right to specify a negative priority here
        channel: the channel to allocate the task to (defaults to the "maven" channel)

        Returns the task ID
        """
        context.session.assertLogin()
        if not context.opts.get('EnableMaven'):
            raise koji.GenericError("Maven support not enabled")
        if not opts:
            opts = {}
        taskOpts = {}
        if priority:
            if priority < 0:
                if not context.session.hasPerm('admin'):
                    raise koji.ActionNotAllowed('only admins may create high-priority tasks')
            taskOpts['priority'] = koji.PRIO_DEFAULT + priority
        if channel:
            taskOpts['channel'] = channel

        return make_task('maven', [url, target, opts], **taskOpts)

    def wrapperRPM(self, build, url, target, priority=None, channel='maven', opts=None):
        """Create a top-level wrapperRPM task

        build: The build to generate wrapper rpms for.  Must be in the COMPLETE state and have no
               rpms already associated with it.
        url: SCM URL to a specfile fragment
        target: The build target to use when building the wrapper rpm.
                The build_tag of the target will be used to populate the buildroot in which the
                rpms are built.
        priority: the amount to increase (or decrease) the task priority, relative
                  to the default priority; higher values mean lower priority; only
                  admins have the right to specify a negative priority here
        channel: the channel to allocate the task to (defaults to the "maven" channel)

        returns the task ID
        """
        context.session.assertLogin()
        if not context.opts.get('EnableMaven'):
            raise koji.GenericError("Maven support not enabled")

        if not opts:
            opts = {}

        build = self.getBuild(build, strict=True)
        if list_rpms(build['id']) and not (opts.get('scratch') or opts.get('create_build')):
            raise koji.PreBuildError('wrapper rpms for %s have already been built' %
                                     koji.buildLabel(build))
        build_target = self.getBuildTarget(target)
        if not build_target:
            raise koji.PreBuildError('no such build target: %s' % target)
        build_tag = self.getTag(build_target['build_tag'], strict=True)
        repo_info = self.getRepo(build_tag['id'])
        if not repo_info:
            raise koji.PreBuildError('no repo for tag: %s' % build_tag['name'])
        opts['repo_id'] = repo_info['id']

        taskOpts = {}
        if priority:
            taskOpts['priority'] = koji.PRIO_DEFAULT + priority
        taskOpts['channel'] = channel

        return make_task('wrapperRPM', [url, build_target, build, None, opts], **taskOpts)

    def chainMaven(self, builds, target, opts=None, priority=None, channel='maven'):
        """Create a Maven chain-build task

        builds: a list of maps defining the parameters for the sequence of builds
        target: the build target
        priority: the amount to increase (or decrease) the task priority, relative
                  to the default priority; higher values mean lower priority; only
                  admins have the right to specify a negative priority here
        channel: the channel to allocate the task to (defaults to the "maven" channel)

        Returns the task ID
        """
        context.session.assertLogin()
        if not context.opts.get('EnableMaven'):
            raise koji.GenericError("Maven support not enabled")
        taskOpts = {}
        if priority:
            if priority < 0:
                if not context.session.hasPerm('admin'):
                    raise koji.ActionNotAllowed('only admins may create high-priority tasks')
            taskOpts['priority'] = koji.PRIO_DEFAULT + priority
        if channel:
            taskOpts['channel'] = channel

        return make_task('chainmaven', [builds, target, opts], **taskOpts)

    def winBuild(self, vm, url, target, opts=None, priority=None, channel='vm'):
        """
        Create a Windows build task

        vm: the name of the VM to run the build in
        url: The url to checkout the source from.  May be a CVS, SVN, or GIT repository.
        opts: task options
        target: the build target
        priority: the amount to increase (or decrease) the task priority, relative
                  to the default priority; higher values mean lower priority; only
                  admins have the right to specify a negative priority here
        channel: the channel to allocate the task to (defaults to the "vm" channel)

        Returns the task ID
        """
        context.session.assertLogin()
        if not context.opts.get('EnableWin'):
            raise koji.GenericError("Windows support not enabled")
        targ_info = self.getBuildTarget(target)
        policy_data = {'vm_name': vm,
                       'tag': targ_info['dest_tag']}
        assert_policy('vm', policy_data)
        if not opts:
            opts = {}
        taskOpts = {}
        if priority:
            if priority < 0:
                if not context.session.hasPerm('admin'):
                    raise koji.ActionNotAllowed('only admins may create high-priority tasks')
            taskOpts['priority'] = koji.PRIO_DEFAULT + priority
        if channel:
            taskOpts['channel'] = channel

        return make_task('winbuild', [vm, url, target, opts], **taskOpts)

    # Create the image task. Called from _build_image in the client.
    #
    def buildImage(self, name, version, arch, target, ksfile, img_type, opts=None, priority=None):
        """
        Create an image using a kickstart file and group package list.
        """

        if img_type not in ('livecd', 'appliance', 'livemedia'):
            raise koji.GenericError('Unrecognized image type: %s' % img_type)

        context.session.assertPerm(img_type)

        taskOpts = {'channel': img_type}
        if img_type == 'livemedia':
            taskOpts['arch'] = 'noarch'
        else:
            taskOpts['arch'] = arch
        if priority:
            if priority < 0:
                if not context.session.hasPerm('admin'):
                    raise koji.ActionNotAllowed(
                        'only admins may create high-priority tasks')

            taskOpts['priority'] = koji.PRIO_DEFAULT + priority

        return make_task(img_type, [name, version, arch, target, ksfile, opts], **taskOpts)

    # Create the image task. Called from _build_image_oz in the client.
    #
    def buildImageIndirection(self, opts=None, priority=None):
        """
        Create an image using two other images and an indirection template
        """
        context.session.assertPerm('image')
        taskOpts = {'channel': 'image'}
        if priority:
            if priority < 0:
                if not context.session.hasPerm('admin'):
                    raise koji.ActionNotAllowed(
                        'only admins may create high-priority tasks')

            taskOpts['priority'] = koji.PRIO_DEFAULT + priority
        if 'scratch' not in opts and 'indirection_template_url' not in opts:
            raise koji.ActionNotAllowed(
                'Non-scratch builds must provide url for the indirection template')

        if 'arch' in opts:
            taskOpts['arch'] = opts['arch']
        return make_task('indirectionimage', [opts], **taskOpts)

    # Create the image task. Called from _build_image_oz in the client.
    #
    def buildImageOz(self, name, version, arches, target, inst_tree, opts=None, priority=None):
        """
        Create an image using a kickstart file and group package list.
        """
        context.session.assertPerm('image')
        taskOpts = {'channel': 'image'}
        if priority:
            if priority < 0:
                if not context.session.hasPerm('admin'):
                    raise koji.ActionNotAllowed(
                        'only admins may create high-priority tasks')

            taskOpts['priority'] = koji.PRIO_DEFAULT + priority
        if 'scratch' not in opts and 'ksurl' not in opts:
            raise koji.ActionNotAllowed('Non-scratch builds must provide ksurl')

        return make_task('image', [name, version, arches, target, inst_tree, opts], **taskOpts)

    def hello(self, *args):
        return "Hello World"

    def fault(self):
        "debugging. raise an error"
        raise Exception("test exception")

    def error(self):
        "debugging. raise an error"
        raise koji.GenericError("test error")

    def echo(self, *args):
        return args

    def getAPIVersion(self):
        return koji.API_VERSION

    def mavenEnabled(self):
        """Get status of maven support"""
        return bool(context.opts.get('EnableMaven'))

    def winEnabled(self):
        """Get status of windows support"""
        return bool(context.opts.get('EnableWin'))

    def showSession(self):
        return "%s" % context.session

    def getSessionInfo(self):
        if not context.session.logged_in:
            return None
        return context.session.session_data

    def showOpts(self):
        """Returns hub options"""
        context.session.assertPerm('admin')
        return "%r" % context.opts

    def getEvent(self, id):
        """
        Get information about the event with the given id.

        A map will be returned with the following keys:
          - id (integer): id of the event
          - ts (float): timestamp the event was created, in
                        seconds since the epoch

        If no event with the given id exists, an error will be raised.
        """
        fields = ('id', 'ts')
        values = {'id': id}
        q = """SELECT id, EXTRACT(EPOCH FROM time) FROM events
                WHERE id = %(id)i"""
        return _singleRow(q, values, fields, strict=True)

    def getLastEvent(self, before=None):
        """
        Get the id and timestamp of the last event recorded in the system.
        Events are usually created as the result of a configuration change
        in the database.

        If "before" (int or float) is specified, return the last event
        that occurred before that time (in seconds since the epoch).
        If there is no event before the given time, an error will be raised.

        Note that due to differences in precision between the database and python,
        this method can return an event with a timestamp the same or slightly higher
        (by a few microseconds) than the value of "before" provided.  Code using this
        method should check that the timestamp returned is in fact lower than the parameter.
        When trying to find information about a specific event, the getEvent() method
        should be used.
        """
        fields = ('id', 'ts')
        values = {}
        q = """SELECT id, EXTRACT(EPOCH FROM time) FROM events"""
        if before is not None:
            if not isinstance(before, NUMERIC_TYPES):
                raise koji.GenericError('invalid type for before: %s' % type(before))
            # use the repr() conversion because it retains more precision than the
            # string conversion
            q += """ WHERE EXTRACT(EPOCH FROM time) < %(before)r"""
            values['before'] = before
        q += """ ORDER BY id DESC LIMIT 1"""
        return _singleRow(q, values, fields, strict=True)

    def makeTask(self, *args, **opts):
        """Creates task manually. This is mainly for debugging, only an admin
        can make arbitrary tasks. You need to supply all *args and **opts
        accordingly to the task."""
        context.session.assertPerm('admin')
        return make_task(*args, **opts)

    def uploadFile(self, path, name, size, md5sum, offset, data, volume=None, checksum=None):
        """upload file to the hub

        Files can be uploaded in chunks, if so the hash and size describe the
        chunk rather than the whole file.

        :param str path: the relative path to upload to
        :param str name: the name of the file
        :param int size: size of contents (bytes)
        :param checksum: MD5 hex digest (see md5sum) or a tuple (hash_type, digest) of contents
        :type checksum: str or tuple
        :param str data: base64 encoded file contents
        :param int offset: The offset indicates where the chunk belongs.
                           The special offset -1 is used to indicate the final
                           chunk.
        :param str md5sum: legacy param name of checksum. md5sum name is misleading,
                           but it is here for backwards compatibility

        :returns: True
        """
        context.session.assertLogin()
        contents = base64.b64decode(data)
        del data
        # we will accept offset and size as strings to work around xmlrpc limits
        offset = koji.decode_int(offset)
        size = koji.decode_int(size)
        if checksum is None and md5sum is not None:
            checksum = md5sum
        if isinstance(checksum, str):
            # this case is for backwards compatibility
            verify = "md5"
            digest = checksum
        elif checksum is None:
            verify = None
        else:
            verify, digest = checksum
        sum_cls = get_verify_class(verify)
        if offset != -1:
            if size is not None:
                if size != len(contents):
                    return False
            if verify is not None:
                if digest != sum_cls(contents).hexdigest():
                    return False
        fn = get_upload_path(path, name, create=True, volume=volume)
        try:
            st = os.lstat(fn)
        except OSError as e:
            if e.errno == errno.ENOENT:
                pass
            else:
                raise
        else:
            if not stat.S_ISREG(st.st_mode):
                raise koji.GenericError("destination not a file: %s" % fn)
            elif offset == 0:
                # first chunk, so file should not exist yet
                if not fn.endswith('.log'):
                    # but we allow .log files to be uploaded multiple times to support
                    # realtime log-file viewing
                    raise koji.GenericError("file already exists: %s" % fn)
        fd = os.open(fn, os.O_RDWR | os.O_CREAT, 0o666)
        # log_error("fd=%r" %fd)
        try:
            if offset == 0 or (offset == -1 and size == len(contents)):
                # truncate file
                fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    os.ftruncate(fd, 0)
                    # log_error("truncating fd %r to 0" %fd)
                finally:
                    fcntl.lockf(fd, fcntl.LOCK_UN)
            if offset == -1:
                os.lseek(fd, 0, 2)
            else:
                os.lseek(fd, offset, 0)
            # write contents
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB, len(contents), 0, 2)
            try:
                os.write(fd, contents)
                # log_error("wrote contents")
            finally:
                fcntl.lockf(fd, fcntl.LOCK_UN, len(contents), 0, 2)
            if offset == -1:
                if size is not None:
                    # truncate file
                    fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    try:
                        os.ftruncate(fd, size)
                        # log_error("truncating fd %r to size %r" % (fd,size))
                    finally:
                        fcntl.lockf(fd, fcntl.LOCK_UN)
                if verify is not None:
                    # check final digest
                    chksum = sum_cls()
                    fcntl.lockf(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
                    try:
                        os.lseek(fd, 0, 0)
                        while True:
                            block = os.read(fd, 819200)
                            if not block:
                                break
                            chksum.update(block)
                        if digest != chksum.hexdigest():
                            return False
                    finally:
                        fcntl.lockf(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
        return True

    def checkUpload(self, path, name, verify=None, tail=None, volume=None):
        """Return basic information about an uploaded file"""
        fn = get_upload_path(path, name, volume=volume)
        data = {}
        try:
            fd = os.open(fn, os.O_RDONLY)
        except OSError as e:
            if e.errno == errno.ENOENT:
                return None
            else:
                raise
        try:
            try:
                fcntl.lockf(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except IOError as e:
                raise koji.LockError(e)
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise koji.GenericError("Not a regular file: %s" % fn)
            data['size'] = st.st_size
            data['mtime'] = st.st_mtime
            if verify:
                chksum = get_verify_class(verify)()
                if tail is not None:
                    if tail < 0:
                        raise koji.GenericError("invalid tail value: %r" % tail)
                    offset = max(st.st_size - tail, 0)
                    os.lseek(fd, offset, 0)
                length = 0
                chunk = os.read(fd, 8192)
                while chunk:
                    length += len(chunk)
                    chksum.update(chunk)
                    chunk = os.read(fd, 8192)
                data['sumlength'] = length
                data['hexdigest'] = chksum.hexdigest()
            return data
        finally:
            # this will also free our lock
            os.close(fd)

    def downloadTaskOutput(self, taskID, fileName, offset=0, size=-1, volume=None):
        """Download the file with the given name, generated by the task with the
        given ID."""
        if '..' in fileName:
            raise koji.GenericError('Invalid file name: %s' % fileName)
        filePath = '%s/%s/%s' % (koji.pathinfo.work(volume),
                                 koji.pathinfo.taskrelpath(taskID),
                                 fileName)
        filePath = os.path.normpath(filePath)
        if not os.path.isfile(filePath):
            raise koji.GenericError('no file "%s" output by task %i' % (fileName, taskID))
        # Let the caller handler any IO or permission errors
        with open(filePath, 'rb') as f:
            if isinstance(offset, str):
                offset = int(offset)
            if offset is not None and offset > 0:
                f.seek(offset, 0)
            elif offset is not None and offset < 0:
                f.seek(offset, 2)
            contents = f.read(size)
        return base64encode(contents)

    listTaskOutput = staticmethod(list_task_output)

    createTag = staticmethod(create_tag)
    editTag = staticmethod(old_edit_tag)
    editTag2 = staticmethod(edit_tag)
    deleteTag = staticmethod(delete_tag)

    createExternalRepo = staticmethod(create_external_repo)
    listExternalRepos = staticmethod(get_external_repos)
    getExternalRepo = staticmethod(get_external_repo)
    editExternalRepo = staticmethod(edit_external_repo)
    deleteExternalRepo = staticmethod(delete_external_repo)

    def addExternalRepoToTag(self, tag_info, repo_info, priority,
                             merge_mode='koji'):
        """Add an external repo to a tag.

        :param tag_info: Tag name or ID number
        :param repo_info: External repository name or ID number
        :param int priority: Priority of this repository for this tag
        :param str merge_mode: This must be one of the values of the
                               koji.REPO_MERGE_MODES set. If unspecified,
                               the default is "koji".
        """
        # wrap the local method so we don't expose the event parameter
        add_external_repo_to_tag(tag_info, repo_info, priority, merge_mode)

    def removeExternalRepoFromTag(self, tag_info, repo_info):
        """
        Remove an external repo from a tag

        :param tag_info: Tag name or ID number
        :param repo_info: External repository name or ID number
        :raises: GenericError if this external repo is not associated
                 with this tag.
        """
        # wrap the local method so we don't expose the event parameter
        remove_external_repo_from_tag(tag_info, repo_info)

    editTagExternalRepo = staticmethod(edit_tag_external_repo)
    getTagExternalRepos = staticmethod(get_tag_external_repos)
    getExternalRepoList = staticmethod(get_external_repo_list)

    resetBuild = staticmethod(reset_build)

    def importArchive(self, filepath, buildinfo, type, typeInfo):
        """
        Import an archive file and associate it with a build.  The archive can
        be any non-rpm filetype supported by Koji.

        filepath: path to the archive file (relative to the Koji workdir)
        buildinfo: information about the build to associate the archive with
                   May be a string (NVR), integer (buildID), or dict (containing keys: name,
                   version, release)
        type: type of the archive being imported.  Currently supported archive types: maven, win
        typeInfo: dict of type-specific information
        """
        if type == 'maven':
            if not context.opts.get('EnableMaven'):
                raise koji.GenericError('Maven support not enabled')
            context.session.assertPerm('maven-import')
        elif type == 'win':
            if not context.opts.get('EnableWin'):
                raise koji.GenericError('Windows support not enabled')
            context.session.assertPerm('win-import')
        elif type == 'image':
            context.session.assertPerm('image-import')
        else:
            raise koji.GenericError('unsupported archive type: %s' % type)
        buildinfo = get_build(buildinfo, strict=True)
        fullpath = '%s/%s' % (koji.pathinfo.work(), filepath)
        import_archive(fullpath, buildinfo, type, typeInfo)

    CGInitBuild = staticmethod(cg_init_build)
    CGRefundBuild = staticmethod(cg_refund_build)
    CGImport = staticmethod(cg_import)

    untaggedBuilds = staticmethod(untagged_builds)
    tagHistory = staticmethod(tag_history)
    queryHistory = staticmethod(query_history)

    deleteBuild = staticmethod(delete_build)

    def buildReferences(self, build, limit=None, lazy=False):
        return build_references(get_build(build, strict=True)['id'], limit, lazy)
    buildReferences.__doc__ = build_references.__doc__

    addVolume = staticmethod(add_volume)
    removeVolume = staticmethod(remove_volume)
    listVolumes = staticmethod(list_volumes)
    changeBuildVolume = staticmethod(change_build_volume)

    def getVolume(self, volume, strict=False):
        """Lookup the given volume

        Returns a dictionary containing the name and id of the matching
        volume, or None if no match.
        If strict is true, raises an error if no match.
        """
        return lookup_name('volume', volume, strict=strict)

    def applyVolumePolicy(self, build, strict=False):
        """Apply the volume policy to a given build

        The volume policy is normally applied at import time, but it can
        also be applied with this call.

        Parameters:
            build: the build to apply the policy to
            strict: if True, raises on exception on policy issues
        """
        context.session.assertPerm('admin')
        build = get_build(build, strict=True)
        return apply_volume_policy(build, strict)

    def createEmptyBuild(self, name, version, release, epoch, owner=None):
        """Creates empty build entry

        :param str name: build name
        :param str version: build version
        :param str release: release version
        :param str epoch: epoch version
        :param userInfo: a str (Kerberos principal or name) or an int (user id)
                         or a dict:
                             - id: User's ID
                             - name: User's name
                             - krb_principal: Kerberos principal
        :return: int build ID
        """
        context.session.assertPerm('admin')
        data = {'name': name, 'version': version, 'release': release,
                'epoch': epoch}
        if owner is not None:
            data['owner'] = owner
        return new_build(data)

    def createMavenBuild(self, build_info, maven_info):
        """
        Associate Maven metadata with an existing build.  The build must
        not already have associated Maven metadata.  maven_info must be a dict
        containing group_id, artifact_id, and version entries.
        """
        context.session.assertPerm('maven-import')
        if not context.opts.get('EnableMaven'):
            raise koji.GenericError("Maven support not enabled")
        build = get_build(build_info)
        if not build:
            build_id = new_build(dslice(build_info, ('name', 'version', 'release', 'epoch')))
            build = get_build(build_id, strict=True)
        new_maven_build(build, maven_info)

    def createWinBuild(self, build_info, win_info):
        """
        Associate Windows metadata with an existing build.  The build must
        not already have associated Windows metadata.  win_info must be a dict
        containing a platform entry.
        """
        context.session.assertPerm('win-import')
        if not context.opts.get('EnableWin'):
            raise koji.GenericError("Windows support not enabled")
        build = get_build(build_info)
        if not build:
            build_id = new_build(dslice(build_info, ('name', 'version', 'release', 'epoch')))
            build = get_build(build_id, strict=True)
        new_win_build(build, win_info)

    def createImageBuild(self, build_info):
        """
        Associate image metadata with an existing build. The build must not
        already have associated image metadata.
        """
        context.session.assertPerm('image-import')
        build = get_build(build_info)
        if not build:
            build_id = new_build(dslice(build_info, ('name', 'version', 'release', 'epoch')))
            build = get_build(build_id, strict=True)
        new_image_build(build)

    def importRPM(self, path, basename):
        """Import an RPM into the database.

        The file must be uploaded first.
        """
        context.session.assertPerm('admin')
        uploadpath = koji.pathinfo.work()
        fn = "%s/%s/%s" % (uploadpath, path, basename)
        if not os.path.exists(fn):
            raise koji.GenericError("No such file: %s" % fn)
        rpminfo = import_rpm(fn)
        import_rpm_file(fn, rpminfo['build'], rpminfo)
        add_rpm_sig(rpminfo['id'], koji.rip_rpm_sighdr(fn))
        for tag in list_tags(build=rpminfo['build_id']):
            set_tag_update(tag['id'], 'IMPORT')

    def mergeScratch(self, task_id):
        """Import the rpms generated by a scratch build, and associate
        them with an existing build.

        To be eligible for import, the build must:
         - be successfully completed
         - contain at least one arch-specific rpm

        The task must:
         - be a 'build' task
         - be successfully completed
         - use the exact same SCM URL as the build
         - contain at least one arch-specific rpm
         - have no overlap between the arches of the rpms it contains and
           the rpms contained by the build
         - contain a .src.rpm whose filename exactly matches the .src.rpm
           of the build

        Only arch-specific rpms will be imported.  noarch rpms and the src
        rpm will be skipped.  Build logs and buildroot metadata from the
        scratch build will be imported along with the rpms.

        This is useful for bootstrapping a new arch.  RPMs can be built
        for the new arch using a scratch build and then merged into an
        existing build, incrementally expanding arch coverage and avoiding
        the need for a mass-rebuild to support the new arch.
        """
        context.session.assertPerm('admin')
        return merge_scratch(task_id)

    def addExternalRPM(self, rpminfo, external_repo, strict=True):
        """Import an external RPM

        This call is mainly for testing. Normal access will be through
        a host call"""
        context.session.assertPerm('admin')
        add_external_rpm(rpminfo, external_repo, strict=strict)

    def tagBuildBypass(self, tag, build, force=False, notify=False):
        """Tag a build without running post checks

        This is a short circuit function for imports.
        Admin or tag permission required.

        Tagging with a locked tag is not allowed unless force is true.
        Retagging is not allowed unless force is true. (retagging changes the order
        of entries will affect which build is the latest)
        """
        context.session.assertPerm('tag')
        tag_id = get_tag(tag, strict=True)['id']
        build_id = get_build(build, strict=True)['id']
        policy_data = {'tag': tag_id, 'build': build_id, 'fromtag': None, 'operation': 'tag'}
        assert_policy('tag', policy_data, force=force)
        _tag_build(tag, build, force=force)
        if notify:
            tag_notification(True, tag, None, build, context.session.user_id)

    def tagBuild(self, tag, build, force=False, fromtag=None):
        """Request that a build be tagged

        The force option will attempt to force the action in the event of:
            - tag locked
            - missing permission
            - package not in list for tag
            - policy violation
        The force option is really only effective for admins

        If fromtag is specified, this becomes a move operation.

        This call creates a task that was originally intended to perform more
        extensive checks, but never has. We're stuck with this task system until
        we're ready to break the api.

        The return value is the task id
        """
        context.session.assertLogin()
        # first some lookups and basic sanity checks
        build = get_build(build, strict=True)
        tag = get_tag(tag, strict=True)
        if fromtag:
            fromtag_id = get_tag_id(fromtag, strict=True)
        else:
            fromtag_id = None
        pkg_id = build['package_id']
        tag_id = tag['id']
        build_id = build['id']
        # build state check
        if build['state'] != koji.BUILD_STATES['COMPLETE']:
            state = koji.BUILD_STATES[build['state']]
            raise koji.TagError("build %s not complete: state %s" % (build['nvr'], state))
        # basic tag access check
        assert_tag_access(tag_id, user_id=None, force=force)
        if fromtag:
            assert_tag_access(fromtag_id, user_id=None, force=force)
        # package list check
        pkgs = readPackageList(tagID=tag_id, pkgID=pkg_id, inherit=True)
        pkg_error = None
        if pkg_id not in pkgs:
            pkg_error = "Package %s not in list for %s" % (build['name'], tag['name'])
        elif pkgs[pkg_id]['blocked']:
            pkg_error = "Package %s blocked in %s" % (build['name'], tag['name'])
        if pkg_error:
            if force and context.session.hasPerm('admin'):
                pkglist_add(tag_id, pkg_id, force=True, block=False)
                logger.info("Package add policy %s/%s overriden by %s" % (
                    tag['name'], build['nvr'], context.session.user_data['name']))
            else:
                raise koji.TagError(pkg_error)
        # tag policy check
        policy_data = {'tag': tag_id, 'build': build_id, 'fromtag': fromtag_id}
        if fromtag is None:
            policy_data['operation'] = 'tag'
        else:
            policy_data['operation'] = 'move'
        # don't check policy for admins using force
        # XXX - we're running this check twice, here and in host.tagBuild (called by the task)
        assert_policy('tag', policy_data, force=force)
        # spawn the tagging task
        return make_task('tagBuild', [tag_id, build_id, force, fromtag_id], priority=10)

    def untagBuild(self, tag, build, strict=True, force=False):
        """Untag a build

        Unlike tagBuild, this does not create a task
        No return value"""
        # we can't staticmethod this one -- we're limiting the options
        context.session.assertLogin()
        user_id = context.session.user_id
        tag_id = get_tag(tag, strict=True)['id']
        build_id = get_build(build, strict=True)['id']
        policy_data = {'tag': None, 'build': build_id, 'fromtag': tag_id}
        policy_data['operation'] = 'untag'
        try:
            # don't check policy for admins using force
            assert_policy('tag', policy_data, force=force)
            _untag_build(tag, build, strict=strict, force=force)
            tag_notification(True, None, tag, build, user_id)
        except Exception:
            exctype, value = sys.exc_info()[:2]
            tag_notification(False, None, tag, build, user_id, False, "%s: %s" % (exctype, value))
            raise

    def untagBuildBypass(self, tag, build, strict=True, force=False, notify=False):
        """Untag a build without any checks

        Admin and tag permission only. Intended for syncs/imports.

        Unlike tagBuild, this does not create a task
        No return value"""
        context.session.assertPerm('tag')
        tag_id = get_tag(tag, strict=True)['id']
        build_id = get_build(build, strict=True)['id']
        policy_data = {'tag': None, 'build': build_id, 'fromtag': tag_id, 'operation': 'untag'}
        assert_policy('tag', policy_data, force=force)
        _untag_build(tag, build, strict=strict, force=force)
        if notify:
            tag_notification(True, None, tag, build, context.session.user_id)

    def moveBuild(self, tag1, tag2, build, force=False):
        """Move a build from tag1 to tag2

        Returns the task id of the task performing the move"""
        return self.tagBuild(tag2, build, force=force, fromtag=tag1)

    def moveAllBuilds(self, tag1, tag2, package, force=False):
        """Move all builds of a package from tag1 to tag2 in the correct order

        Returns the task id of the task performing the move"""

        context.session.assertLogin()
        # lookups and basic sanity checks
        pkg_id = get_package_id(package, strict=True)
        tag1_id = get_tag_id(tag1, strict=True)
        tag2_id = get_tag_id(tag2, strict=True)

        # note: we're just running the quick checks now so we can fail
        #       early if appropriate, rather then waiting for the task
        # Make sure package is on the list for the tag we're adding it to
        pkgs = readPackageList(tagID=tag2_id, pkgID=pkg_id, inherit=True)
        pkg_error = None
        if pkg_id not in pkgs:
            pkg_error = "Package %s not in list for tag %s" % (package, tag2)
        elif pkgs[pkg_id]['blocked']:
            pkg_error = "Package %s blocked in tag %s" % (package, tag2)
        if pkg_error:
            if force and context.session.hasPerm('admin'):
                pkglist_add(tag2_id, pkg_id, force=True, block=False)
                logger.info("Package list policy %s/%s overriden by %s" % (
                    tag2, package, context.session.user_data['name']))
            else:
                raise koji.TagError(pkg_error)

        # access check
        assert_tag_access(tag1_id, user_id=None, force=force)
        assert_tag_access(tag2_id, user_id=None, force=force)

        build_list = readTaggedBuilds(tag1_id, package=package)
        # we want 'ORDER BY tag_listing.create_event ASC' not DESC so reverse
        build_list.reverse()

        # policy check
        policy_data = {'tag': tag2, 'fromtag': tag1, 'operation': 'move'}
        # don't check policy for admins using force
        for build in build_list:
            policy_data['build'] = build['id']
            assert_policy('tag', policy_data)
            # XXX - we're running this check twice, here and in host.tagBuild (called by the
            # task)

        wait_on = []
        tasklist = []
        for build in build_list:
            task_id = make_task('dependantTask',
                                [wait_on, [['tagBuild',
                                            [tag2_id, build['id'], force, tag1_id],
                                            {'priority': 15}]]])
            wait_on = [task_id]
            log_error("\nMade Task: %s\n" % task_id)
            tasklist.append(task_id)
        return tasklist

    listTags = staticmethod(list_tags)

    getBuild = staticmethod(get_build)
    getBuildLogs = staticmethod(get_build_logs)
    getNextRelease = staticmethod(get_next_release)
    getMavenBuild = staticmethod(get_maven_build)
    getWinBuild = staticmethod(get_win_build)
    getImageBuild = staticmethod(get_image_build)
    getBuildType = staticmethod(get_build_type)
    getArchiveTypes = staticmethod(get_archive_types)
    getArchiveType = staticmethod(get_archive_type)
    listArchives = staticmethod(list_archives)
    getArchive = staticmethod(get_archive)
    getMavenArchive = staticmethod(get_maven_archive)
    getWinArchive = staticmethod(get_win_archive)
    getImageArchive = staticmethod(get_image_archive)
    listArchiveFiles = staticmethod(list_archive_files)
    getArchiveFile = staticmethod(get_archive_file)

    listBTypes = staticmethod(list_btypes)
    addBType = staticmethod(add_btype)

    addArchiveType = staticmethod(add_archive_type)

    def getChangelogEntries(self, buildID=None, taskID=None, filepath=None, author=None,
                            before=None, after=None, queryOpts=None, strict=False):
        """Get changelog entries for the build with the given ID,
           or for the rpm generated by the given task at the given path

        - author: only return changelogs with a matching author
        - before: only return changelogs from before the given date (in UTC)
                  (a datetime object, a string in the 'YYYY-MM-DD HH24:MI:SS format, or integer
                  seconds since the epoch)
        - after: only return changelogs from after the given date (in UTC)
                 (a datetime object, a string in the 'YYYY-MM-DD HH24:MI:SS format, or integer
                 seconds since the epoch)
        - queryOpts: query options used by the QueryProcessor
        - strict: if srpm doesn't exist raise an error, otherwise return empty list

        If "order" is not specified in queryOpts, results will be returned in reverse chronological
        order.

        Results will be returned as a list of maps with 'date', 'author', and 'text' keys.
        If there are no results, an empty list will be returned.
        """
        if queryOpts is None:
            queryOpts = {}
        if queryOpts.get('order') in ('date', '-date'):
            # use a numeric sort on the timestamp instead of an alphabetic sort on the
            # date string
            queryOpts['order'] = queryOpts['order'].replace('date', 'date_ts')
        if buildID:
            build_info = get_build(buildID)
            if not build_info:
                if strict:
                    raise koji.GenericError("Build %s doesn't exist" % buildID)
                return _applyQueryOpts([], queryOpts)
            srpms = self.listRPMs(buildID=build_info['id'], arches='src')
            if not srpms:
                if strict:
                    raise koji.GenericError("Build %s doesn't have srpms" % buildID)
                return _applyQueryOpts([], queryOpts)
            srpm_info = srpms[0]
            srpm_path = joinpath(koji.pathinfo.build(build_info), koji.pathinfo.rpm(srpm_info))
        elif taskID:
            if not filepath:
                raise koji.GenericError('filepath must be specified with taskID')
            if filepath.startswith('/') or '../' in filepath:
                raise koji.GenericError('invalid filepath: %s' % filepath)
            srpm_path = joinpath(koji.pathinfo.work(),
                                 koji.pathinfo.taskrelpath(taskID),
                                 filepath)
        else:
            raise koji.GenericError('either buildID or taskID and filepath must be specified')

        if not os.path.exists(srpm_path):
            if strict:
                raise koji.GenericError("SRPM %s doesn't exist" % srpm_path)
            else:
                return _applyQueryOpts([], queryOpts)

        if before:
            if isinstance(before, datetime.datetime):
                before = calendar.timegm(before.utctimetuple())
            elif isinstance(before, str):
                before = koji.util.parseTime(before)
            elif isinstance(before, int):
                pass
            else:
                raise koji.GenericError('invalid type for before: %s' % type(before))

        if after:
            if isinstance(after, datetime.datetime):
                after = calendar.timegm(after.utctimetuple())
            elif isinstance(after, str):
                after = koji.util.parseTime(after)
            elif isinstance(after, int):
                pass
            else:
                raise koji.GenericError('invalid type for after: %s' % type(after))

        results = []

        fields = koji.get_header_fields(srpm_path,
                                        ['changelogtime', 'changelogname', 'changelogtext'])
        for (cltime, clname, cltext) in zip(fields['changelogtime'], fields['changelogname'],
                                            fields['changelogtext']):
            cldate = datetime.datetime.fromtimestamp(cltime).isoformat(' ')
            clname = koji.fixEncoding(clname)
            cltext = koji.fixEncoding(cltext)

            if author and author != clname:
                continue
            if before and not cltime < before:
                continue
            if after and not cltime > after:
                continue

            if queryOpts.get('asList'):
                results.append([cldate, clname, cltext])
            else:
                results.append({'date': cldate,
                                'date_ts': cltime,
                                'author': clname,
                                'text': cltext})

        results = _applyQueryOpts(results, queryOpts)
        return koji.fixEncodingRecurse(results, remove_nonprintable=True)

    def cancelBuild(self, buildID):
        """Cancel the build with the given buildID

        If the build is associated with a task, cancel the task as well.
        Return True if the build was successfully canceled, False if not."""
        context.session.assertLogin()
        build = get_build(buildID)
        if build is None:
            return False
        if build['owner_id'] != context.session.user_id:
            if not context.session.hasPerm('admin'):
                raise koji.ActionNotAllowed('Cannot cancel build, not owner')
        return cancel_build(build['id'])

    def assignTask(self, task_id, host, force=False):
        """Assign a task to a host

        Specify force=True to assign a non-free task
        """
        context.session.assertPerm('admin')
        task = Task(task_id)
        host = get_host(host, strict=True)
        return task.assign(host['id'], force)

    def freeTask(self, task_id):
        """Free a task"""
        context.session.assertPerm('admin')
        task = Task(task_id)
        task.free()

    def cancelTask(self, task_id, recurse=True):
        """Cancel a task"""
        task = Task(task_id)
        if not task.verifyOwner() and not task.verifyHost():
            if not context.session.hasPerm('admin'):
                raise koji.ActionNotAllowed('Cannot cancel task, not owner')
        # non-admins can also use cancelBuild
        task.cancel(recurse=recurse)

    def cancelTaskFull(self, task_id, strict=True):
        """Cancel a task and all tasks in its group"""
        context.session.assertPerm('admin')
        # non-admins can use cancelBuild or cancelTask
        Task(task_id).cancelFull(strict=strict)

    def cancelTaskChildren(self, task_id):
        """Cancel a task's children, but not the task itself"""
        context.session.assertLogin()
        task = Task(task_id)
        if not task.verifyOwner() and not task.verifyHost():
            if not context.session.hasPerm('admin'):
                raise koji.ActionNotAllowed('Cannot cancel task, not owner')
        task.cancelChildren()

    def setTaskPriority(self, task_id, priority, recurse=True):
        """Set task priority"""
        context.session.assertPerm('admin')
        task = Task(task_id)
        if task.isFinished():
            raise koji.GenericError("Finished task's priority can't be updated")
        task.setPriority(priority, recurse=recurse)

    def listTagged(self, tag, event=None, inherit=False, prefix=None, latest=False, package=None,
                   owner=None, type=None):
        """List builds tagged with tag"""
        # lookup tag id
        tag = get_tag(tag, strict=True, event=event)['id']
        results = readTaggedBuilds(tag, event, inherit=inherit, latest=latest, package=package,
                                   owner=owner, type=type)
        if prefix:
            prefix = prefix.lower()
            results = [build for build in results
                       if build['package_name'].lower().startswith(prefix)]
        return results

    def listTaggedRPMS(self, tag, event=None, inherit=False, latest=False, package=None, arch=None,
                       rpmsigs=False, owner=None, type=None):
        """List rpms and builds within tag"""
        # lookup tag id
        tag = get_tag(tag, strict=True, event=event)['id']
        return readTaggedRPMS(tag, event=event, inherit=inherit, latest=latest, package=package,
                              arch=arch, rpmsigs=rpmsigs, owner=owner, type=type)

    def listTaggedArchives(self, tag, event=None, inherit=False, latest=False, package=None,
                           type=None):
        """List archives and builds within a tag"""
        # lookup tag id
        tag = get_tag(tag, strict=True, event=event)['id']
        return readTaggedArchives(tag, event=event, inherit=inherit, latest=latest,
                                  package=package, type=type)

    def listBuilds(self, packageID=None, userID=None, taskID=None, prefix=None, state=None,
                   volumeID=None, source=None,
                   createdBefore=None, createdAfter=None,
                   completeBefore=None, completeAfter=None, type=None, typeInfo=None,
                   queryOpts=None):
        """Return a list of builds that match the given parameters

        Filter parameters
            - packageID: only builds of the specified package (numeric id)
            - userID: only builds owned by the given user (numeric id)
            - taskID: only builds with the given task ID
                If taskID is -1, only builds with a non-null task id
            - volumeID: only builds stored on the given volume (numeric id)
            - source: only builds where the source field matches (glob pattern)
            - prefix: only builds whose package name starts with that prefix
            - state: only builds in the given state (numeric value)

        Timestamp filter parameters
            - these limit the results to builds where the corresponding
                timestamp is before or after the given time
            - the time value may be specified as seconds since the epoch or
                in ISO format ('YYYY-MM-DD HH24:MI:SS')
            - filters for creation_time:
                - createdBefore
                - createdAfter
            - filters for completion_time:
                - completeBefore
                - completeAfter

        Build type parameters:
            - type: only builds of the given btype (such as maven or image)
            - typeInfo: only builds with matching type-specific info (given
                as a dictionary). Can only be used in conjunction with the
                type parameter. Only limited types are supported.

                For type=maven, the provided group_id, artifact_id, and/or version
                fields are matched

                For type=win, the provided platform fields are matched

        Returns a list of maps.  Each map contains the following keys:

          - build_id
          - version
          - release
          - epoch
          - state
          - package_id
          - package_name
          - name (same as package_name)
          - nvr (synthesized for sorting purposes)
          - owner_id
          - owner_name
          - volume_id
          - volume_name
          - source
          - creation_event_id
          - creation_time
          - creation_ts
          - start_time
          - start_ts
          - completion_time
          - completion_ts
          - task_id
          - extra

        If type == 'maven', each map will also contain the following keys:

          - maven_group_id
          - maven_artifact_id
          - maven_version

        If type == 'win', each map will also contain the following key:

            - platform

        If no builds match, an empty list is returned.
        """
        fields = [('build.id', 'build_id'), ('build.version', 'version'),
                  ('build.release', 'release'),
                  ('build.epoch', 'epoch'), ('build.state', 'state'),
                  ('build.completion_time', 'completion_time'),
                  ('build.start_time', 'start_time'),
                  ('build.source', 'source'),
                  ('build.extra', 'extra'),
                  ('events.id', 'creation_event_id'), ('events.time', 'creation_time'),
                  ('build.task_id', 'task_id'),
                  ('EXTRACT(EPOCH FROM events.time)', 'creation_ts'),
                  ('EXTRACT(EPOCH FROM build.start_time)', 'start_ts'),
                  ('EXTRACT(EPOCH FROM build.completion_time)', 'completion_ts'),
                  ('package.id', 'package_id'), ('package.name', 'package_name'),
                  ('package.name', 'name'),
                  ('volume.id', 'volume_id'), ('volume.name', 'volume_name'),
                  ("package.name || '-' || build.version || '-' || build.release", 'nvr'),
                  ('users.id', 'owner_id'), ('users.name', 'owner_name')]

        tables = ['build']
        joins = ['LEFT JOIN events ON build.create_event = events.id',
                 'LEFT JOIN package ON build.pkg_id = package.id',
                 'LEFT JOIN volume ON build.volume_id = volume.id',
                 'LEFT JOIN users ON build.owner = users.id']
        clauses = []
        if packageID is not None:
            clauses.append('package.id = %(packageID)i')
        if userID is not None:
            clauses.append('users.id = %(userID)i')
        if volumeID is not None:
            clauses.append('volume.id = %(volumeID)i')
        if taskID is not None:
            if taskID == -1:
                clauses.append('build.task_id IS NOT NULL')
            else:
                clauses.append('build.task_id = %(taskID)i')
        if source is not None:
            source = self._prepareSearchTerms(source, 'glob')
            clauses.append('build.source ilike %(source)s')
        if prefix:
            clauses.append("package.name ilike %(prefix)s || '%%'")
        if state is not None:
            clauses.append('build.state = %(state)i')
        if createdBefore:
            if not isinstance(createdBefore, str):
                createdBefore = datetime.datetime.fromtimestamp(createdBefore).isoformat(' ')
            clauses.append('events.time < %(createdBefore)s')
        if createdAfter:
            if not isinstance(createdAfter, str):
                createdAfter = datetime.datetime.fromtimestamp(createdAfter).isoformat(' ')
            clauses.append('events.time > %(createdAfter)s')
        if completeBefore:
            if not isinstance(completeBefore, str):
                completeBefore = datetime.datetime.fromtimestamp(completeBefore).isoformat(' ')
            clauses.append('build.completion_time < %(completeBefore)s')
        if completeAfter:
            if not isinstance(completeAfter, str):
                completeAfter = datetime.datetime.fromtimestamp(completeAfter).isoformat(' ')
            clauses.append('build.completion_time > %(completeAfter)s')
        if type is None:
            pass
        elif type == 'maven':
            joins.append('maven_builds ON build.id = maven_builds.build_id')
            fields.extend([('maven_builds.group_id', 'maven_group_id'),
                           ('maven_builds.artifact_id', 'maven_artifact_id'),
                           ('maven_builds.version', 'maven_version')])
            if typeInfo:
                if 'group_id' in typeInfo:
                    clauses.append('maven_builds.group_id = %(group_id)s')
                    group_id = typeInfo['group_id']
                if 'artifact_id' in typeInfo:
                    clauses.append('maven_builds.artifact_id = %(artifact_id)s')
                    artifact_id = typeInfo['artifact_id']
                if 'version' in typeInfo:
                    clauses.append('maven_builds.version = %(version)s')
                    version = typeInfo['version']
        elif type == 'win':
            joins.append('win_builds ON build.id = win_builds.build_id')
            fields.append(('win_builds.platform', 'platform'))
            if typeInfo:
                clauses.append('win_builds.platform = %(platform)s')
                platform = typeInfo['platform']
        elif type == 'image':
            joins.append('image_builds ON build.id = image_builds.build_id')
            fields.append(('image_builds.build_id', 'build_id'))
        else:
            btype = lookup_name('btype', type, strict=False)
            if not btype:
                raise koji.GenericError('unsupported build type: %s' % type)
            btype_id = btype['id']
            joins.append('build_types ON build.id = build_types.build_id '
                         'AND btype_id = %(btype_id)s')

        query = QueryProcessor(columns=[pair[0] for pair in fields],
                               aliases=[pair[1] for pair in fields],
                               tables=tables, joins=joins, clauses=clauses,
                               transform=_fix_extra_field,
                               values=locals(), opts=queryOpts)

        return query.iterate()

    def getLatestBuilds(self, tag, event=None, package=None, type=None):
        """List latest builds for tag (inheritance enabled)"""
        if not isinstance(tag, int):
            # lookup tag id
            tag = get_tag_id(tag, strict=True)
        return readTaggedBuilds(tag, event, inherit=True, latest=True, package=package, type=type)

    def getLatestRPMS(self, tag, package=None, arch=None, event=None, rpmsigs=False, type=None):
        """List latest RPMS for tag (inheritance enabled)"""
        if not isinstance(tag, int):
            # lookup tag id
            tag = get_tag_id(tag, strict=True)
        return readTaggedRPMS(tag, package=package, arch=arch, event=event, inherit=True,
                              latest=True, rpmsigs=rpmsigs, type=type)

    def getLatestMavenArchives(self, tag, event=None, inherit=True):
        """Return a list of the latest Maven archives in the tag, as of the given event
           (or now if event is None).  If inherit is True, follow the tag hierarchy
           and return a list of the latest archives for all tags in the tree."""
        tag_id = get_tag_id(tag, strict=True)
        return maven_tag_archives(tag_id, event_id=event, inherit=inherit)

    def getAverageBuildDuration(self, package):
        """Get the average duration of a build of the given package.
        Returns a floating-point value indicating the
        average number of seconds the package took to build.  If the package
        has never been built, return None."""
        packageID = get_package_id(package)
        if not packageID:
            return None
        st_complete = koji.BUILD_STATES['COMPLETE']
        query = """SELECT EXTRACT(epoch FROM avg(build.completion_time - events.time))
                     FROM build
                     JOIN events ON build.create_event = events.id
                     WHERE build.pkg_id = %(packageID)i
                       AND build.state = %(st_complete)i
                       AND build.task_id IS NOT NULL"""

        return _singleValue(query, locals())

    packageListAdd = staticmethod(pkglist_add)
    packageListRemove = staticmethod(pkglist_remove)
    packageListBlock = staticmethod(pkglist_block)
    packageListUnblock = staticmethod(pkglist_unblock)
    packageListSetOwner = staticmethod(pkglist_setowner)
    packageListSetArches = staticmethod(pkglist_setarches)

    groupListAdd = staticmethod(grplist_add)
    groupListRemove = staticmethod(grplist_remove)
    groupListBlock = staticmethod(grplist_block)
    groupListUnblock = staticmethod(grplist_unblock)

    groupPackageListAdd = staticmethod(grp_pkg_add)
    groupPackageListRemove = staticmethod(grp_pkg_remove)
    groupPackageListBlock = staticmethod(grp_pkg_block)
    groupPackageListUnblock = staticmethod(grp_pkg_unblock)

    groupReqListAdd = staticmethod(grp_req_add)
    groupReqListRemove = staticmethod(grp_req_remove)
    groupReqListBlock = staticmethod(grp_req_block)
    groupReqListUnblock = staticmethod(grp_req_unblock)

    getTagGroups = staticmethod(readTagGroups)

    checkTagAccess = staticmethod(check_tag_access)

    getGlobalInheritance = staticmethod(readGlobalInheritance)

    def getInheritanceData(self, tag, event=None):
        """Return inheritance data for tag"""
        tag = get_tag_id(tag, strict=True)
        return readInheritanceData(tag, event)

    def setInheritanceData(self, tag, data, clear=False):
        """
        Set inheritance relationships for a tag.

        This tag will be the "child" that inherits from a list of "parents".

        :param tag: The koji tag that will inherit from parent tags.
        :type tag: int or str
        :param list data: Inheritance rules to set for this child tag. This is
                          a list of rules (dicts) for parent tags and
                          priorities. If any rule dict in the list has a
                          special "delete link": True key and value, Koji will
                          remove this inheritance rule instead of adding it.
        :param bool clear: Wipe out all existing inheritance rules and only
                           apply the ones you submit here. If unspecified,
                           this defaults to False.
        """
        # verify existence of tag and/or convert name to id
        tag = get_tag_id(tag, strict=True)
        context.session.assertPerm('tag')
        return writeInheritanceData(tag, data, clear=clear)

    def getFullInheritance(self, tag, event=None, reverse=False, stops=None, jumps=None):
        """
        :param int|str tag: tag ID | name
        :param int event: event ID
        :param bool reverse: return reversed tree (descendants instead of
                             parents)
        :param dict stops: dict of tag ids which should be ignored
        :param dict jumps: dict of tag ids which should be skipped

        :returns: list of node dicts
        """
        if stops is None:
            stops = {}
        if jumps is None:
            jumps = {}
        if not isinstance(tag, int):
            # lookup tag id
            tag = get_tag_id(tag, strict=True)
        for mapping in [stops, jumps]:
            for key in to_list(mapping.keys()):
                mapping[int(key)] = mapping[key]
        return readFullInheritance(tag, event, reverse, stops, jumps)

    listRPMs = staticmethod(list_rpms)

    def listBuildRPMs(self, build):
        """Get information about all the RPMs generated by the build with the given
        ID.  A list of maps is returned, each map containing the following keys:

        - id
        - name
        - version
        - release
        - arch
        - epoch
        - payloadhash
        - size
        - buildtime
        - build_id
        - buildroot_id

        If no build has the given ID, or the build generated no RPMs, an empty list is returned."""
        if not isinstance(build, int):
            # lookup build id
            build = self.findBuildID(build, strict=True)
        return self.listRPMs(buildID=build)

    getRPM = staticmethod(get_rpm)

    def getRPMDeps(self, rpmID, depType=None, queryOpts=None, strict=False):
        """Return dependency information about the RPM with the given ID.
        If depType is specified, restrict results to dependencies of the given type.
        Otherwise, return all dependency information.  A list of maps will be returned,
        each with the following keys:
        - name
        - version
        - flags
        - type

        If there is no *internal* RPM with the given ID, or no RPM file found,
        an empty list will be returned, unless strict is True in which case a
        GenericError is raised.
        If the RPM has no dependency information, an empty list will be returned.
        """
        if queryOpts is None:
            queryOpts = {}
        rpm_info = get_rpm(rpmID, strict=strict)
        if not rpm_info:
            return _applyQueryOpts([], queryOpts)
        if rpm_info and not rpm_info['build_id']:
            if strict:
                raise koji.GenericError("Can not get dependencies,"
                                        " because RPM: %s is not internal" % rpmID)
            return _applyQueryOpts([], queryOpts)
        build_info = get_build(rpm_info['build_id'])
        rpm_path = joinpath(koji.pathinfo.build(build_info),
                            koji.pathinfo.rpm(rpm_info))
        if not os.path.exists(rpm_path):
            if strict:
                raise koji.GenericError("RPM file of %s doesn't exist" % rpmID)
            return _applyQueryOpts([], queryOpts)

        results = []

        for dep_name in ['REQUIRE', 'PROVIDE', 'CONFLICT', 'OBSOLETE', 'SUGGEST', 'ENHANCE',
                         'SUPPLEMENT', 'RECOMMEND']:
            dep_id = getattr(koji, 'DEP_' + dep_name)
            if depType is None or depType == dep_id:
                fields = koji.get_header_fields(rpm_path, [dep_name + 'NAME',
                                                           dep_name + 'VERSION',
                                                           dep_name + 'FLAGS'])
                for (name, version, flags) in zip(fields[dep_name + 'NAME'],
                                                  fields[dep_name + 'VERSION'],
                                                  fields[dep_name + 'FLAGS']):
                    if queryOpts.get('asList'):
                        results.append([name, version, flags, dep_id])
                    else:
                        results.append(
                            {'name': name, 'version': version, 'flags': flags, 'type': dep_id})

        return _applyQueryOpts(results, queryOpts)

    def listRPMFiles(self, rpmID, queryOpts=None):
        """List files associated with the RPM with the given ID.  A list of maps
        will be returned, each with the following keys:
        - name
        - digest
        - md5 (alias for digest)
        - digest_algo
        - size
        - flags

        If there is no RPM with the given ID, or that RPM contains no files,
        an empty list will be returned."""
        if queryOpts is None:
            queryOpts = {}
        rpm_info = get_rpm(rpmID)
        if not rpm_info or not rpm_info['build_id']:
            return _applyQueryOpts([], queryOpts)
        build_info = get_build(rpm_info['build_id'])
        rpm_path = joinpath(koji.pathinfo.build(build_info), koji.pathinfo.rpm(rpm_info))
        if not os.path.exists(rpm_path):
            return _applyQueryOpts([], queryOpts)

        results = []
        hdr = koji.get_rpm_header(rpm_path)
        fields = koji.get_header_fields(hdr, ['filenames', 'filemd5s', 'filesizes', 'fileflags',
                                              'fileusername', 'filegroupname', 'filemtimes',
                                              'filemodes'])
        digest_algo = koji.util.filedigestAlgo(hdr)

        for (name, digest, size, flags, user, group, mtime, mode) \
                in zip(fields['filenames'], fields['filemd5s'],
                       fields['filesizes'], fields['fileflags'],
                       fields['fileusername'], fields['filegroupname'],
                       fields['filemtimes'], fields['filemodes']):
            if queryOpts.get('asList'):
                results.append([name, digest, size, flags, digest_algo, user, group, mtime, mode])
            else:
                results.append({'name': name, 'digest': digest, 'digest_algo': digest_algo,
                                'md5': digest, 'size': size, 'flags': flags,
                                'user': user, 'group': group, 'mtime': mtime, 'mode': mode})

        return _applyQueryOpts(results, queryOpts)

    def getRPMFile(self, rpmID, filename, strict=False):
        """
        Get info about the file in the given RPM with the given filename.
        A map will be returned with the following keys:
        - rpm_id
        - name
        - digest
        - md5 (alias for digest)
        - digest_algo
        - size
        - flags
        - user
        - group
        - mtime
        - mode

        If there is no *internal* RPM with the given ID, or no RPM file found,
        an empty map will be returned, unless strict is True in which case a
        GenericError is raised.
        If no such file exists, an empty map will be returned, unless strict is
        True in which case a GenericError is raised.
        """
        rpm_info = get_rpm(rpmID, strict=strict)
        if not rpm_info:
            return {}
        if rpm_info and not rpm_info['build_id']:
            if strict:
                raise koji.GenericError("Can not get RPM file,"
                                        " because RPM: %s is not internal" % rpmID)
            return {}
        build_info = get_build(rpm_info['build_id'])
        rpm_path = joinpath(koji.pathinfo.build(build_info), koji.pathinfo.rpm(rpm_info))
        if not os.path.exists(rpm_path):
            if strict:
                raise koji.GenericError(
                    "RPM package file of %s doesn't exist" % rpmID)
            return {}

        hdr = koji.get_rpm_header(rpm_path)
        # use filemd5s for backward compatibility
        fields = koji.get_header_fields(hdr, ['filenames', 'filemd5s', 'filesizes', 'fileflags',
                                              'fileusername', 'filegroupname', 'filemtimes',
                                              'filemodes'])
        digest_algo = koji.util.filedigestAlgo(hdr)

        i = 0
        for name in fields['filenames']:
            if name == filename:
                return {'rpm_id': rpm_info['id'], 'name': name, 'digest': fields['filemd5s'][i],
                        'digest_algo': digest_algo, 'md5': fields['filemd5s'][i],
                        'size': fields['filesizes'][i], 'flags': fields['fileflags'][i],
                        'user': fields['fileusername'][i], 'group': fields['filegroupname'][i],
                        'mtime': fields['filemtimes'][i], 'mode': fields['filemodes'][i]}
            i += 1
        if strict:
            raise koji.GenericError(
                "No file: %s found in RPM: %s" % (filename, rpmID))
        return {}

    def getRPMHeaders(self, rpmID=None, taskID=None, filepath=None, headers=None):
        """
        Get the requested headers from the rpm.  Header names are case-insensitive.
        If a header is requested that does not exist an exception will be raised.
        Returns a map of header names to values.  If the specified ID
        is not valid or the rpm does not exist on the file system, an empty map
        will be returned.
        """
        if not headers:
            headers = []
        if rpmID:
            rpm_info = get_rpm(rpmID)
            if not rpm_info or not rpm_info['build_id']:
                return {}
            build_info = get_build(rpm_info['build_id'])
            rpm_path = joinpath(koji.pathinfo.build(build_info), koji.pathinfo.rpm(rpm_info))
            if not os.path.exists(rpm_path):
                return {}
        elif taskID:
            if not filepath:
                raise koji.GenericError('filepath must be specified with taskID')
            if filepath.startswith('/') or '../' in filepath:
                raise koji.GenericError('invalid filepath: %s' % filepath)
            rpm_path = joinpath(koji.pathinfo.work(),
                                koji.pathinfo.taskrelpath(taskID),
                                filepath)
        else:
            raise koji.GenericError('either rpmID or taskID and filepath must be specified')

        headers = koji.get_header_fields(rpm_path, headers)
        return koji.fixEncodingRecurse(headers, remove_nonprintable=True)

    queryRPMSigs = staticmethod(query_rpm_sigs)

    def writeSignedRPM(self, an_rpm, sigkey, force=False):
        """Write a signed copy of the rpm"""
        context.session.assertPerm('sign')
        # XXX - still not sure if this is the right restriction
        return write_signed_rpm(an_rpm, sigkey, force)

    def addRPMSig(self, an_rpm, data):
        """Store a signature header for an rpm

        data: the signature header encoded as base64
        """
        context.session.assertPerm('sign')
        return add_rpm_sig(an_rpm, base64.b64decode(data))

    findBuildID = staticmethod(find_build_id)
    getTagID = staticmethod(get_tag_id)
    getTag = staticmethod(get_tag)

    def getPackageID(self, name, strict=False):
        """Get package ID by name.
        If package doesn't exist, return None, unless strict is True in which
        case an exception is raised."""
        query = QueryProcessor(tables=['package'],
                               columns=['id'],
                               clauses=['name=%(name)s'],
                               values=locals())
        r = query.executeOne()
        if not r:
            if strict:
                raise koji.GenericError('Invalid package name: %s' % name)
            return None
        return r['id']

    getPackage = staticmethod(lookup_package)

    def listPackages(self, tagID=None, userID=None, pkgID=None, prefix=None, inherited=False,
                     with_dups=False, event=None, queryOpts=None):
        """List if tagID and/or userID is specified, limit the
        list to packages belonging to the given user or with the
        given tag.

        A list of maps is returned.  Each map contains the
        following keys:

        - package_id
        - package_name

        If tagID, userID, or pkgID are specified, the maps will also contain the
        following keys.

        - tag_id
        - tag_name
        - owner_id
        - owner_name
        - extra_arches
        - blocked
        """
        if tagID is None and userID is None and pkgID is None:
            return self.listPackagesSimple(prefix, queryOpts)
        else:
            if tagID is not None:
                tagID = get_tag_id(tagID, strict=True)
            if userID is not None:
                userID = get_user(userID, strict=True)['id']
            if pkgID is not None:
                pkgID = get_package_id(pkgID, strict=True)
            result_list = list(readPackageList(tagID=tagID, userID=userID, pkgID=pkgID,
                                               inherit=inherited, with_dups=with_dups,
                                               event=event).values())
            if with_dups:
                # when with_dups=True, readPackageList returns a list of list of dicts
                # convert it to a list of dicts for consistency
                results = []
                for result in result_list:
                    results.extend(result)
            else:
                results = result_list

        if prefix:
            prefix = prefix.lower()
            results = [package for package in results
                       if package['package_name'].lower().startswith(prefix)]

        return _applyQueryOpts(results, queryOpts)

    def listPackagesSimple(self, prefix=None, queryOpts=None):
        """list packages that starts with prefix and are filted
        and ordered by queryOpts.

        Args:
            prefix: default is None. If is not None will filter out
                packages which name doesn't start with the prefix.
            queryOpts: query options used by the QueryProcessor.

        Returns:
            A list of maps is returned, and each map contains key
            'package_name' and 'package_id'.
        """
        fields = (('package.id', 'package_id'),
                  ('package.name', 'package_name'))
        if prefix is None:
            clauses = None
        else:
            clauses = ["""package.name ILIKE %(prefix)s || '%%'"""]
        query = QueryProcessor(
            tables=['package'], clauses=clauses, values=locals(),
            columns=[f[0] for f in fields], aliases=[f[1] for f in fields],
            opts=queryOpts)
        return query.execute()

    def checkTagPackage(self, tag, pkg):
        """Check that pkg is in the list for tag. Returns true/false"""
        tag_id = get_tag_id(tag, strict=False)
        pkg_id = get_package_id(pkg, strict=False)
        if pkg_id is None or tag_id is None:
            return False
        pkgs = readPackageList(tagID=tag_id, pkgID=pkg_id, inherit=True)
        if pkg_id not in pkgs:
            return False
        else:
            # still might be blocked
            return not pkgs[pkg_id]['blocked']

    def getPackageConfig(self, tag, pkg, event=None):
        """Get config for package in tag"""
        tag_id = get_tag_id(tag, strict=False)
        pkg_id = get_package_id(pkg, strict=False)
        if pkg_id is None or tag_id is None:
            return None
        pkgs = readPackageList(tagID=tag_id, pkgID=pkg_id, inherit=True, event=event)
        return pkgs.get(pkg_id, None)

    getUser = staticmethod(get_user)
    editUser = staticmethod(edit_user)

    def grantPermission(self, userinfo, permission, create=False):
        """Grant a permission to a user"""
        context.session.assertPerm('admin')
        user_id = get_user(userinfo, strict=True)['id']
        perm = lookup_perm(permission, strict=(not create), create=create)
        perm_id = perm['id']
        if perm['name'] in koji.auth.get_user_perms(user_id):
            raise koji.GenericError('user %s already has permission: %s' %
                                    (userinfo, perm['name']))
        insert = InsertProcessor('user_perms')
        insert.set(user_id=user_id, perm_id=perm_id)
        insert.make_create()
        insert.execute()

    def revokePermission(self, userinfo, permission):
        """Revoke a permission from a user"""
        context.session.assertPerm('admin')
        user_id = get_user(userinfo, strict=True)['id']
        perm = lookup_perm(permission, strict=True)
        perm_id = perm['id']
        if perm['name'] not in koji.auth.get_user_perms(user_id):
            raise koji.GenericError('user %s does not have permission: %s' %
                                    (userinfo, perm['name']))
        update = UpdateProcessor('user_perms', values=locals(),
                                 clauses=["user_id = %(user_id)i", "perm_id = %(perm_id)i"])
        update.make_revoke()
        update.execute()

    def createUser(self, username, status=None, krb_principal=None):
        """Add a user to the database

        :param str username: The username for this Koji user.
        :param int status: This must be one of the values of the
                           koji.USER_STATUS enum. If unspecified,
                           the default is koji.USER_STATUS['NORMAL'].
        :param str krb_principal: a custom Kerberos principal, or None.
        :raises: GenericError if the user or Kerberos principal already
                 exists.
        """
        context.session.assertPerm('admin')
        if get_user(username):
            raise koji.GenericError('user already exists: %s' % username)
        if krb_principal and get_user_by_krb_principal(krb_principal):
            raise koji.GenericError(
                'user with this Kerberos principal already exists: %s'
                % krb_principal)

        return context.session.createUser(username, status=status,
                                          krb_principal=krb_principal)

    def addUserKrbPrincipal(self, user, krb_principal):
        """Add a Kerberos principal for user"""
        context.session.assertPerm('admin')
        userinfo = get_user(user, strict=True)
        if not krb_principal:
            raise koji.GenericError('krb_principal must be specified')
        if get_user_by_krb_principal(krb_principal):
            raise koji.GenericError(
                'user with this Kerberos principal already exists: %s'
                % krb_principal)
        return context.session.setKrbPrincipal(userinfo['name'], krb_principal)

    def removeUserKrbPrincipal(self, user, krb_principal):
        """remove a Kerberos principal for user"""
        context.session.assertPerm('admin')
        userinfo = get_user(user, strict=True)
        if not krb_principal:
            raise koji.GenericError('krb_principal must be specified')
        return context.session.removeKrbPrincipal(userinfo['name'],
                                                  krb_principal)

    def enableUser(self, username):
        """Enable logins by the specified user"""
        user = get_user(username)
        if not user:
            raise koji.GenericError('unknown user: %s' % username)
        set_user_status(user, koji.USER_STATUS['NORMAL'])

    def disableUser(self, username):
        """Disable logins by the specified user"""
        user = get_user(username)
        if not user:
            raise koji.GenericError('unknown user: %s' % username)
        set_user_status(user, koji.USER_STATUS['BLOCKED'])

    listCGs = staticmethod(list_cgs)
    grantCGAccess = staticmethod(grant_cg_access)
    revokeCGAccess = staticmethod(revoke_cg_access)

    # group management calls
    newGroup = staticmethod(new_group)
    addGroupMember = staticmethod(add_group_member)
    dropGroupMember = staticmethod(drop_group_member)
    getGroupMembers = staticmethod(get_group_members)

    def listUsers(self, userType=koji.USERTYPES['NORMAL'], prefix=None, queryOpts=None):
        """List all users in the system.
        userType can be an integer value from koji.USERTYPES (defaults to 0,
        i.e. normal users).  Returns a list of maps with the following keys:

        - id
        - name
        - status
        - usertype
        - krb_principals

        If no users of the specified
        type exist, return an empty list."""
        fields = ('id', 'name', 'status', 'usertype',
                  'array_agg(krb_principal)')
        aliases = ('id', 'name', 'status', 'usertype', 'krb_principals')
        joins = ('LEFT JOIN user_krb_principals'
                 ' ON users.id = user_krb_principals.user_id',)
        clauses = ['usertype = %(userType)i']
        if prefix:
            clauses.append("name ilike %(prefix)s || '%%'")
        if queryOpts is None:
            queryOpts = {}
        if not queryOpts.get('group'):
            queryOpts['group'] = 'users.id'
        else:
            raise koji.GenericError('queryOpts.group is not available for this API')
        query = QueryProcessor(columns=fields, aliases=aliases,
                               tables=('users',), joins=joins, clauses=clauses,
                               values=locals(), opts=queryOpts,
                               enable_group=True, transform=xform_user_krb)
        return query.execute()

    def getBuildConfig(self, tag, event=None):
        """Return build configuration associated with a tag"""
        taginfo = get_tag(tag, strict=True, event=event)
        order = readFullInheritance(taginfo['id'], event=event)
        # follow inheritance for arches and extra
        for link in order:
            if link['noconfig']:
                continue
            ancestor = get_tag(link['parent_id'], strict=True, event=event)
            if taginfo['arches'] is None and ancestor['arches'] is not None:
                taginfo['arches'] = ancestor['arches']
            for key in ancestor['extra']:
                if key not in taginfo['extra']:
                    taginfo['extra'][key] = ancestor['extra'][key]
        return taginfo

    def getRepo(self, tag, state=None, event=None, dist=False):
        """Get individual repository data based on tag and additional filters.
        If more repos fits, most recent is returned.

        :param int|str tag: tag ID or name
        :param int state: value from koji.REPO_STATES
        :param int event: event ID
        :param bool dist: True = dist repo, False = regular repo

        :returns: dict with repo data (id, state, create_event, time, dist)
        """
        if isinstance(tag, int):
            id = tag
        else:
            id = get_tag_id(tag, strict=True)

        fields = ['repo.id', 'repo.state', 'repo.create_event', 'events.time',
                  'EXTRACT(EPOCH FROM events.time)', 'repo.dist']
        aliases = ['id', 'state', 'create_event', 'creation_time', 'create_ts', 'dist']
        joins = ['events ON repo.create_event = events.id']
        clauses = ['repo.tag_id = %(id)i']
        if dist:
            clauses.append('repo.dist is true')
        else:
            clauses.append('repo.dist is false')
        if event:
            # the repo table doesn't have all the fields of a _config table, just create_event
            clauses.append('create_event <= %(event)i')
        else:
            if state is None:
                state = koji.REPO_READY
            clauses.append('repo.state = %(state)s')

        query = QueryProcessor(columns=fields, aliases=aliases,
                               tables=['repo'], joins=joins, clauses=clauses,
                               values=locals(),
                               opts={'order': '-creation_time', 'limit': 1})
        return query.executeOne()

    repoInfo = staticmethod(repo_info)
    getActiveRepos = staticmethod(get_active_repos)

    def distRepo(self, tag, keys, **task_opts):
        """Create a dist-repo task. returns task id"""
        if not context.session.hasPerm('dist-repo') and not context.session.hasPerm('admin'):
            assert_policy('dist_repo', {'tag': tag})
        repo_id, event_id = dist_repo_init(tag, keys, task_opts)
        task_opts['event'] = event_id
        # cancel potentially running distRepos
        build_config = self.getBuildConfig(tag)
        if build_config['extra'].get('distrepo.cancel_others', False):
            tasks = self.listTasks(opts={
                'state': [koji.TASK_STATES['FREE'],
                          koji.TASK_STATES['OPEN'],
                          koji.TASK_STATES['ASSIGNED']],
                'method': 'distRepo',
                'decode': True})
            # filter only for this tag
            task_ids = [t['id'] for t in tasks if t['request'][0] == tag]
            for task_id in task_ids:
                logger.debug("Cancelling distRepo task %d" % task_id)
                Task(task_id).cancel(recurse=True)
        return make_task('distRepo', [tag, repo_id, keys, task_opts],
                         priority=15, channel='createrepo')

    def newRepo(self, tag, event=None, src=False, debuginfo=False, separate_src=False):
        """Create a newRepo task. returns task id"""
        if context.session.hasPerm('regen-repo'):
            pass
        else:
            context.session.assertPerm('repo')
        # raise error when tag does not exist
        get_tag(tag, strict=True, event=event)
        opts = {}
        if event is not None:
            opts['event'] = event
        if src:
            opts['src'] = True
        if separate_src:
            opts['separate_src'] = True
        if debuginfo:
            opts['debuginfo'] = True
        args = koji.encode_args(tag, **opts)
        return make_task('newRepo', args, priority=15, channel='createrepo')

    def repoExpire(self, repo_id):
        """mark repo expired"""
        context.session.assertPerm('repo')
        repo_expire(repo_id)

    def repoDelete(self, repo_id):
        """Attempt to mark repo deleted, return number of references

        If the number of references is nonzero, no change is made
        Does not remove from disk"""
        context.session.assertPerm('repo')
        return repo_delete(repo_id)

    def repoProblem(self, repo_id):
        """mark repo as broken"""
        context.session.assertPerm('repo')
        repo_problem(repo_id)

    tagChangedSinceEvent = staticmethod(tag_changed_since_event)
    createBuildTarget = staticmethod(create_build_target)
    editBuildTarget = staticmethod(edit_build_target)
    deleteBuildTarget = staticmethod(delete_build_target)
    getBuildTargets = staticmethod(get_build_targets)
    getBuildTarget = staticmethod(get_build_target)

    def taskFinished(self, taskId):
        """Returns True if task is finished

        :param int task: id of task queried

        :returns bool: task not/finished
        """
        task = Task(taskId)
        return task.isFinished()

    def getTaskRequest(self, taskId):
        """Return original task request as a list. Content depends on task type

        :param int taskId: id of task queried

        :returns list: request
        """
        task = Task(taskId)
        return task.getRequest()

    def getTaskResult(self, taskId, raise_fault=True):
        """Returns task results depending on task type. For buildArch it is a dict with build info,
        for newRepo list with two items, etc.

        :param int taskId: id of task queried
        :param bool raise_fault: if task's result is a fault, raise it also here, otherwise
                                just get dict with error code/message

        :returns any: dict/list/etc. with task result"""
        task = Task(taskId)
        return task.getResult(raise_fault=raise_fault)

    def getTaskInfo(self, task_id, request=False, strict=False):
        """Get information about a task

        :param int task_id: Task id
        :param bool request: if True, return also task's request
        :param bool strict: raise exception, if task is not found

        :returns dict: task info"""
        single = True
        if isinstance(task_id, (list, tuple)):
            single = False
        else:
            task_id = [task_id]
        ret = [Task(id).getInfo(strict, request) for id in task_id]
        if single:
            return ret[0]
        else:
            return ret

    def getTaskChildren(self, task_id, request=False, strict=False):
        """Return a list of the children
        of the Task with the given ID."""
        task = Task(task_id)
        if strict:
            # check, that task_id is real
            task.getInfo(strict=True)
        return task.getChildren(request=request)

    def getTaskDescendents(self, task_id, request=False):
        """Get all descendents of the task with the given ID.
        Return a map of task_id -> list of child tasks.  If the given
        task has no descendents, the map will contain a single elements
        mapping the given task ID to an empty list.  Map keys will be strings
        representing integers, due to limitations in xmlrpclib.  If "request"
        is true, the parameters sent with the xmlrpc request will be decoded and
        included in the map."""
        task = Task(task_id)
        return get_task_descendents(task, request=request)

    def listTasks(self, opts=None, queryOpts=None):
        """Return list of tasks filtered by options

        Options(dictionary):
            option[type]: meaning
            arch[list]: limit to tasks for given arches
            not_arch[list]: limit to tasks without the given arches
            state[list]: limit to tasks of given state
            not_state[list]: limit to tasks not of the given state
            owner[int|list]: limit to tasks owned by the user with the given ID
            not_owner[int|list]: limit to tasks not owned by the user with the given ID
            host_id[int|list]: limit to tasks running on the host with the given ID
            not_host_id[int|list]: limit to tasks running on the hosts with IDs other than the
                                   given ID
            channel_id[int|list]: limit to tasks in the specified channel
            not_channel_id[int|list]: limit to tasks not in the specified channel
            parent[int|list]: limit to tasks with the given parent
            not_parent[int|list]: limit to tasks without the given parent
            decode[bool]: whether or not xmlrpc data in the 'request' and 'result'
                          fields should be decoded; defaults to False
            method[str]: limit to tasks of the given method
            createdBefore[float or str]: limit to tasks whose create_time is before the
                                         given date, in either float (seconds since the epoch)
                                         or str (ISO) format
            createdAfter[float or str]: limit to tasks whose create_time is after the
                                        given date, in either float (seconds since the epoch)
                                        or str (ISO) format
            startedBefore[float or str]: limit to tasks whose start_time is before the
                                         given date, in either float (seconds since the epoch)
                                         or str (ISO) format
            startedAfter[float or str]: limit to tasks whose start_time is after the
                                        given date, in either float (seconds since the epoch)
                                        or str (ISO) format
            completeBefore[float or str]: limit to tasks whose completion_time is before
                                         the given date, in either float (seconds since the epoch)
                                         or str (ISO) format
            completeAfter[float or str]: limit to tasks whose completion_time is after
                                         the given date, in either float (seconds since the epoch)
                                         or str (ISO) format
        """
        if not opts:
            opts = {}
        if not queryOpts:
            queryOpts = {}
        countOnly = queryOpts.get('countOnly', False)

        tables = ['task']
        if countOnly:
            joins = []
        else:
            joins = ['LEFT JOIN users ON task.owner = users.id']
        flist = Task.fields + (
            ('task.request', 'request'),
            ('task.result', 'result'),
        )
        if not countOnly:
            flist += (
                ('users.name', 'owner_name'),
                ('users.usertype', 'owner_type'),
            )
        fields = [f[0] for f in flist]
        aliases = [f[1] for f in flist]

        conditions = []

        for f in ['arch', 'state']:
            # Include list types
            if f in opts:
                conditions.append('%s IN %%(%s)s' % (f, f))
            # Exclude list types
            if ('not_' + f) in opts:
                conditions.append('%s NOT IN %%(not_%s)s' % (f, f))

        for f in ['owner', 'host_id', 'channel_id', 'parent']:
            # Include int types
            if f in opts:
                if opts[f] is None:
                    conditions.append('%s IS NULL' % f)
                elif isinstance(opts[f], list):
                    conditions.append('%s IN %%(%s)s' % (f, f))
                else:
                    conditions.append('%s = %%(%s)i' % (f, f))
            # Exclude int types
            if ('not_' + f) in opts:
                if opts['not_' + f] is None:
                    conditions.append('%s IS NOT NULL' % f)
                elif isinstance(opts['not_' + f], list):
                    conditions.append('%s NOT IN %%(not_%s)s' % (f, f))
                else:
                    conditions.append('%s != %%(not_%s)i' % (f, f))

        if 'method' in opts:
            conditions.append('method = %(method)s')

        time_opts = [
            ['createdBefore', 'create_time', '<'],
            ['createdAfter', 'create_time', '>'],
            ['startedBefore', 'start_time', '<'],
            ['startedAfter', 'start_time', '>'],
            ['completeBefore', 'completion_time', '<'],
            ['completeAfter', 'completion_time', '>'],
            # and a couple aliases for api compat:
            ['completedBefore', 'completion_time', '<'],
            ['completedAfter', 'completion_time', '>'],
        ]
        for key, field, cmp in time_opts:
            if opts.get(key) is not None:
                value = opts[key]
                if not isinstance(value, str):
                    opts[key] = datetime.datetime.fromtimestamp(value).isoformat(' ')
                conditions.append('%(field)s %(cmp)s %%(%(key)s)s' % locals())

        query = QueryProcessor(columns=fields, aliases=aliases, tables=tables, joins=joins,
                               clauses=conditions, values=opts, opts=queryOpts)
        tasks = query.iterate()
        if queryOpts and (queryOpts.get('countOnly') or queryOpts.get('asList')):
            # Either of the above options makes us unable to easily the decode
            # the xmlrpc data
            return tasks

        if opts.get('decode') and not queryOpts.get('countOnly'):
            if queryOpts.get('asList'):
                keys = []
                for n, f in aliases:
                    if f in ('request', 'result'):
                        keys.append(n)
            else:
                keys = ('request', 'result')
            tasks = self._decode_tasks(tasks, keys)

        return tasks

    def _decode_tasks(self, tasks, keys):
        for task in tasks:
            # decode xmlrpc data
            for f in keys:
                val = task[f]
                if val:
                    try:
                        if val.find('<?xml', 0, 10) == -1:
                            # handle older base64 encoded data
                            val = base64.b64decode(val)
                        # note: loads accepts either bytes or string
                        data, method = xmlrpc.client.loads(val)
                    except xmlrpc.client.Fault as fault:
                        data = fault
                    task[f] = data
            yield task

    def taskReport(self, owner=None):
        """Return data on active or recent tasks"""
        fields = (
            ('task.id', 'id'),
            ('task.state', 'state'),
            ('task.create_time', 'create_time'),
            ('task.completion_time', 'completion_time'),
            ('task.channel_id', 'channel_id'),
            ('channels.name', 'channel'),
            ('task.host_id', 'host_id'),
            ('host.name', 'host'),
            ('task.parent', 'parent'),
            ('task.waiting', 'waiting'),
            ('task.awaited', 'awaited'),
            ('task.method', 'method'),
            ('task.arch', 'arch'),
            ('task.priority', 'priority'),
            ('task.weight', 'weight'),
            ('task.owner', 'owner_id'),
            ('users.name', 'owner'),
            ('build.id', 'build_id'),
            ('package.name', 'build_name'),
            ('build.version', 'build_version'),
            ('build.release', 'build_release'),
        )
        q = """SELECT %s FROM task
        JOIN channels ON task.channel_id = channels.id
        JOIN users ON task.owner = users.id
        LEFT OUTER JOIN host ON task.host_id = host.id
        LEFT OUTER JOIN build ON build.task_id = task.id
        LEFT OUTER JOIN package ON build.pkg_id = package.id
        WHERE (task.state NOT IN (%%(CLOSED)d,%%(CANCELED)d,%%(FAILED)d)
            OR NOW() - task.create_time < '1 hour'::interval)
            """ % ','.join([f[0] for f in fields])
        if owner:
            q += """AND users.id = %s
            """ % get_user(owner, strict=True)['id']
        q += """ORDER BY priority,create_time
        """
        # XXX hard-coded interval
        c = context.cnx.cursor()
        c.execute(q, koji.TASK_STATES)
        return [dict(zip([f[1] for f in fields], row)) for row in c.fetchall()]

    def resubmitTask(self, taskID):
        """Retry a canceled or failed task, using the same parameter as the original task.
        The logged-in user must be the owner of the original task or an admin."""
        context.session.assertLogin()
        task = Task(taskID)
        if not (task.isCanceled() or task.isFailed()):
            raise koji.GenericError('only canceled or failed tasks may be resubmitted')
        taskInfo = task.getInfo()
        if taskInfo['parent'] is not None:
            raise koji.GenericError('only top-level tasks may be resubmitted')
        if not (context.session.user_id == taskInfo['owner'] or self.hasPerm('admin')):
            raise koji.GenericError('only the task owner or an admin may resubmit a task')

        args = task.getRequest()
        channel = get_channel(taskInfo['channel_id'], strict=True)

        return make_task(taskInfo['method'], args,
                         arch=taskInfo['arch'], channel=channel['name'],
                         priority=taskInfo['priority'])

    def addHost(self, hostname, arches, krb_principal=None, force=False):
        """
        Add a builder host to the database.

        :param str hostname: name for the host entry (fqdn recommended).
        :param list arches: list of architectures this builder supports.
        :param str krb_principal: (optional) a non-default kerberos principal
                                  for the host.
        :param bool force: override user type
        :returns: new host id

        If krb_principal is not given then that field will be generated
        from the HostPrincipalFormat setting (if available).
        """
        context.session.assertPerm('host')
        # validate arches
        arches = " ".join(arches)
        arches = koji.parse_arches(arches, strict=True)
        if get_host(hostname):
            raise koji.GenericError('host already exists: %s' % hostname)
        q = """SELECT id FROM channels WHERE name = 'default'"""
        default_channel = _singleValue(q)
        # builder user can already exist, if host tried to log in before adding into db
        userinfo = {'name': hostname}
        if krb_principal:
            userinfo['krb_principal'] = krb_principal
        user = get_user(userInfo=userinfo)
        if user:
            if user['usertype'] != koji.USERTYPES['HOST']:
                if force and user['usertype'] == koji.USERTYPES['NORMAL']:
                    # override usertype in this special case
                    update = UpdateProcessor('users',
                                             values={'userID': user['id']},
                                             clauses=['id = %(userID)i'])
                    update.set(usertype=koji.USERTYPES['HOST'])
                    update.execute()
                else:
                    raise koji.GenericError(
                        'user %s already exists and it is not a host' % hostname)
            userID = user['id']
        else:
            if krb_principal is None:
                fmt = context.opts.get('HostPrincipalFormat')
                if fmt:
                    krb_principal = fmt % hostname
            userID = context.session.createUser(hostname, usertype=koji.USERTYPES['HOST'],
                                                krb_principal=krb_principal)
        # host entry
        hostID = _singleValue("SELECT nextval('host_id_seq')", strict=True)
        insert = "INSERT INTO host (id, user_id, name) VALUES (%(hostID)i, %(userID)i, " \
                 "%(hostname)s)"
        _dml(insert, dslice(locals(), ('hostID', 'userID', 'hostname')))

        insert = InsertProcessor('host_config')
        insert.set(host_id=hostID, arches=arches)
        insert.make_create()
        insert.execute()

        # host_channels entry
        insert = InsertProcessor('host_channels')
        insert.set(host_id=hostID, channel_id=default_channel)
        insert.make_create()
        insert.execute()

        return hostID

    def enableHost(self, hostname):
        """Mark a host as enabled"""
        set_host_enabled(hostname, True)

    def disableHost(self, hostname):
        """Mark a host as disabled"""
        set_host_enabled(hostname, False)

    getHost = staticmethod(get_host)
    editHost = staticmethod(edit_host)
    addHostToChannel = staticmethod(add_host_to_channel)
    removeHostFromChannel = staticmethod(remove_host_from_channel)
    renameChannel = staticmethod(rename_channel)
    removeChannel = staticmethod(remove_channel)

    def listHosts(self, arches=None, channelID=None, ready=None, enabled=None, userID=None,
                  queryOpts=None):
        """Get a list of hosts.  "arches" is a list of string architecture
        names, e.g. ['i386', 'ppc64'].  If one of the arches associated with a given
        host appears in the list, it will be included in the results.  If "ready" and "enabled"
        are specified, only hosts with the given value for the respective field will
        be included."""
        clauses = ['host_config.active IS TRUE']
        joins = ['host ON host.id = host_config.host_id']
        if arches is not None:
            if not arches:
                raise koji.GenericError('arches option cannot be empty')
            # include the regex constraints below so we can match 'ppc' without
            # matching 'ppc64'
            if not isinstance(arches, (list, tuple)):
                arches = [arches]
            archPattern = r'\m(%s)\M' % '|'.join(arches)
            clauses.append('arches ~ %(archPattern)s')
        if channelID is not None:
            channelID = get_channel_id(channelID, strict=True)
            joins.append('host_channels ON host.id = host_channels.host_id')
            clauses.append('host_channels.channel_id = %(channelID)i')
            clauses.append('host_channels.active IS TRUE')
        if ready is not None:
            if ready:
                clauses.append('ready IS TRUE')
            else:
                clauses.append('ready IS FALSE')
        if enabled is not None:
            if enabled:
                clauses.append('enabled IS TRUE')
            else:
                clauses.append('enabled IS FALSE')
        if userID is not None:
            userID = get_user(userID, strict=True)['id']
            clauses.append('user_id = %(userID)i')

        fields = {'host.id': 'id',
                  'host.user_id': 'user_id',
                  'host.name': 'name',
                  'host.ready': 'ready',
                  'host.task_load': 'task_load',
                  'host_config.arches': 'arches',
                  'host_config.capacity': 'capacity',
                  'host_config.description': 'description',
                  'host_config.comment': 'comment',
                  'host_config.enabled': 'enabled',
                  }
        tables = ['host_config']
        fields, aliases = zip(*fields.items())
        query = QueryProcessor(columns=fields, aliases=aliases,
                               tables=tables, joins=joins, clauses=clauses, values=locals())
        return query.execute()

    def getLastHostUpdate(self, hostID):
        """Return the latest update timestampt for the host

        The timestamp represents the last time the host with the given
        ID contacted the hub. Returns None if the host has never contacted
         the hub."""
        query = """SELECT update_time FROM sessions
        JOIN host ON sessions.user_id = host.user_id
        WHERE host.id = %(hostID)i
        ORDER BY update_time DESC
        LIMIT 1
        """
        return _singleValue(query, locals(), strict=False)

    getAllArches = staticmethod(get_all_arches)

    getChannel = staticmethod(get_channel)
    listChannels = staticmethod(list_channels)

    getBuildroot = staticmethod(get_buildroot)

    def getBuildrootListing(self, id):
        """Return a list of packages in the buildroot"""
        br = BuildRoot(id)
        return br.getList()

    listBuildroots = staticmethod(query_buildroots)

    def hasPerm(self, perm, strict=False):
        """Check if the logged-in user has the given permission.  Return False if
        they do not have the permission, or if they are not logged-in."""
        if strict and not lookup_perm(perm):
            raise koji.GenericError('No such permission %s defined' % perm)
        return context.session.hasPerm(perm)

    def getPerms(self):
        """Get a list of the permissions granted to the currently logged-in user."""
        return context.session.getPerms()

    def getUserPerms(self, userID=None):
        """Get a list of the permissions granted to the user with the given ID/name.
        Options:
        - userID: User ID or username. If no userID provided, current login user's
                  permissions will be listed."""
        user_info = get_user(userID, strict=True)
        return koji.auth.get_user_perms(user_info['id'])

    def getAllPerms(self):
        """Get a list of all permissions in the system.  Returns a list of maps.  Each
        map contains the following keys:

        - id
        - name
        """
        query = """SELECT id, name FROM permissions
        ORDER BY id"""

        return _multiRow(query, {}, ['id', 'name'])

    def getLoggedInUser(self):
        """Return information about the currently logged-in user.  Returns data
        in the same format as getUser(), plus the authtype.  If there is no
        currently logged-in user, return None."""
        if context.session.logged_in:
            me = self.getUser(context.session.user_id)
            me['authtype'] = context.session.authtype
            # backward compatible for cli moshimoshi, but it's not real
            if me.get('krb_principals'):
                me['krb_principal'] = me['krb_principals'][0]
            else:
                me['krb_principal'] = None
            return me
        else:
            return None

    def setBuildOwner(self, build, user):
        """Sets owner of a build

        :param int|str|dict build: build ID, NVR or dict with name, version and release
        :param user: a str (Kerberos principal or name) or an int (user id)
                     or a dict:
                         - id: User's ID
                         - name: User's name
                         - krb_principal: Kerberos principal

        :returns: None
        """
        context.session.assertPerm('admin')
        buildinfo = get_build(build, strict=True)
        userinfo = get_user(user, strict=True)
        userid = userinfo['id']
        buildid = buildinfo['id']
        owner_id_old = buildinfo['owner_id']
        koji.plugin.run_callbacks('preBuildStateChange',
                                  attribute='owner_id', old=owner_id_old, new=userid,
                                  info=buildinfo)
        q = """UPDATE build SET owner=%(userid)i WHERE id=%(buildid)i"""
        _dml(q, locals())
        buildinfo = get_build(build, strict=True)
        koji.plugin.run_callbacks('postBuildStateChange',
                                  attribute='owner_id', old=owner_id_old, new=userid,
                                  info=buildinfo)

    def setBuildTimestamp(self, build, ts):
        """Set the completion time for a build

        build should a valid nvr or build id
        ts should be # of seconds since epoch or optionally an
            xmlrpc DateTime value"""
        context.session.assertPerm('admin')
        buildinfo = get_build(build, strict=True)
        if isinstance(ts, xmlrpc.client.DateTime):
            # not recommended
            # the xmlrpclib.DateTime class is almost useless
            try:
                ts = time.mktime(time.strptime(str(ts), '%Y%m%dT%H:%M:%S'))
            except ValueError:
                raise koji.GenericError("Invalid time: %s" % ts)
        elif not isinstance(ts, NUMERIC_TYPES):
            raise koji.GenericError("Invalid type for timestamp")
        ts_old = buildinfo['completion_ts']
        koji.plugin.run_callbacks('preBuildStateChange',
                                  attribute='completion_ts', old=ts_old, new=ts, info=buildinfo)
        buildid = buildinfo['id']
        q = """UPDATE build
        SET completion_time=TIMESTAMP 'epoch' AT TIME ZONE 'utc' + '%(ts)f seconds'::interval
        WHERE id=%%(buildid)i""" % locals()
        _dml(q, locals())
        buildinfo = get_build(build, strict=True)
        koji.plugin.run_callbacks('postBuildStateChange',
                                  attribute='completion_ts', old=ts_old, new=ts, info=buildinfo)

    def count(self, methodName, *args, **kw):
        """Execute the XML-RPC method with the given name and count the results.
        A method return value of None will return O, a return value of type "list", "tuple", or
        "dict" will return len(value), and a return value of any other type will return 1. An
        invalid methodName will raise GenericError."""
        try:
            method = getattr(self, methodName)
        except AttributeError:
            raise koji.GenericError("method %s doesn't exist" % methodName)
        result = method(*args, **kw)
        if result is None:
            return 0
        elif isinstance(result, (list, tuple, dict)):
            return len(result)
        else:
            return 1

    @staticmethod
    def _sortByKeyFuncNoneGreatest(key):
        """Return a function to sort a list of maps by the given key.
        None will sort higher than all other values (instead of lower).
        """
        def internal_key(obj):
            v = obj[key]
            # Nones has priority, others are second
            return (v is None, v)
        return internal_key

    def filterResults(self, methodName, *args, **kw):
        """Execute the XML-RPC method with the given name and filter the results
        based on the options specified in the keywork option "filterOpts".  The method
        must return a list of maps.  Any other return type will result in a GenericError.
        Currently supported options are:
        - offset: the number of elements to trim off the front of the list
        - limit: the maximum number of results to return
        - order: the map key to use to sort the list; the list will be sorted before
                 offset or limit are applied
        - noneGreatest: when sorting, consider 'None' to be greater than all other values;
                        python considers None less than all other values, but Postgres sorts
                        NULL higher than all other values; default to True for consistency
                        with database sorts
        """
        return self.countAndFilterResults(methodName, *args, **kw)[1]

    def countAndFilterResults(self, methodName, *args, **kw):
        """Filter results by a given name and count total results account.

        Execute the XML-RPC method with the given name and filter the results
        based on the options specified in the keywork option "filterOpts".
        The method must return a list of maps.  Any other return type will
        result in a GenericError.

        Args:
        offset: the number of elements to trim off the front of the list
        limit: the maximum number of results to return
        order: the map key to use to sort the list; the list will be sorted
            before offset or limit are applied
        noneGreatest: when sorting, consider 'None' to be greater than all
            other values; python considers None less than all other values,
            but Postgres sorts NULL higher than all other values; default
            to True for consistency with database sorts

        Returns:
            Tuple of total results amount and the filtered results.
        """
        filterOpts = kw.pop('filterOpts', {})

        try:
            method = getattr(self, methodName)
        except AttributeError:
            raise koji.GenericError("method %s doesn't exist" % methodName)
        try:
            results = method(*args, **kw)
        except Exception as ex:
            raise koji.GenericError("method %s raised an exception (%s)" % (methodName, str(ex)))

        if results is None:
            return 0, None
        elif isinstance(results, list):
            _count = len(results)
        else:
            _count = 1

        if not isinstance(results, list):
            raise koji.GenericError('%s() did not return a list' % methodName)

        order = filterOpts.get('order')
        if order:
            if order.startswith('-'):
                reverse = True
                order = order[1:]
            else:
                reverse = False
            if filterOpts.get('noneGreatest', True):
                results.sort(key=self._sortByKeyFuncNoneGreatest(order), reverse=reverse)
            else:
                results.sort(key=order, reverse=reverse)

        offset = filterOpts.get('offset')
        if offset is not None:
            results = results[offset:]
        limit = filterOpts.get('limit')
        if limit is not None:
            results = results[:limit]

        return _count, results

    def getBuildNotifications(self, userID=None):
        """Get build notifications for the user with the given ID, name or
        Kerberos principal. If no user is specified, get the notifications for
        the currently logged-in user. If there is no currently logged-in user,
        raise a GenericError."""
        userID = get_user(userID, strict=True)['id']
        return get_build_notifications(userID)

    def getBuildNotification(self, id, strict=False):
        """Get the build notification with the given ID.
        If there is no notification with the given ID, when strict is True,
        raise GenericError, else return None.
        """
        query = QueryProcessor(tables=['build_notifications'],
                               columns=('id', 'user_id', 'package_id', 'tag_id',
                                        'success_only', 'email'),
                               clauses=['id = %(id)i'],
                               values=locals())
        result = query.executeOne()
        if strict and not result:
            raise koji.GenericError("No notification with ID %i found" % id)
        return result

    def getBuildNotificationBlocks(self, userID=None):
        """Get build notifications for the user with the given ID, name or
        Kerberos principal. If no user is specified, get the notifications for
        the currently logged-in user. If there is no currently logged-in user,
        raise a GenericError."""
        userID = get_user(userID, strict=True)['id']
        return get_build_notification_blocks(userID)

    def getBuildNotificationBlock(self, id, strict=False):
        """Get the build notification with the given ID.
        If there is no notification with the given ID, when strict is True,
        raise GenericError, else return None.
        """
        query = QueryProcessor(tables=['build_notifications_block'],
                               columns=('id', 'user_id', 'package_id', 'tag_id'),
                               clauses=['id = %(id)i'],
                               values=locals())
        result = query.executeOne()
        if strict and not result:
            raise koji.GenericError("No notification block with ID %i found" % id)
        return result

    def updateNotification(self, id, package_id, tag_id, success_only):
        """Update an existing build notification with new data.  If the notification
        with the given ID doesn't exist, or the currently logged-in user is not the
        owner or the notification or an admin, raise a GenericError."""
        currentUser = self.getLoggedInUser()
        if not currentUser:
            raise koji.GenericError('not logged-in')

        orig_notif = self.getBuildNotification(id, strict=True)
        if not (orig_notif['user_id'] == currentUser['id'] or self.hasPerm('admin')):
            raise koji.GenericError('user %i cannot update notifications for user %i' %
                                    (currentUser['id'], orig_notif['user_id']))

        # sanitize input
        if package_id is not None:
            package_id = get_package_id(package_id, strict=True)
        if tag_id is not None:
            tag_id = get_tag_id(tag_id, strict=True)
        success_only = bool(success_only)

        # check existing notifications to not have same twice
        for notification in get_build_notifications(orig_notif['user_id']):
            if (notification['package_id'] == package_id and
                notification['tag_id'] == tag_id and
                    notification['success_only'] == success_only):
                raise koji.GenericError('notification already exists')

        update = UpdateProcessor('build_notifications',
                                 clauses=['id = %(id)i'], values=locals())
        update.set(package_id=package_id, tag_id=tag_id, success_only=success_only)
        update.execute()

    def createNotification(self, user_id, package_id, tag_id, success_only):
        """Create a new notification.  If the user_id does not match the currently logged-in user
        and the currently logged-in user is not an admin, raise a GenericError."""
        currentUser = self.getLoggedInUser()
        if not currentUser:
            raise koji.GenericError('not logged in')

        notificationUser = self.getUser(user_id)
        if not notificationUser:
            raise koji.GenericError('invalid user ID: %s' % user_id)

        if not (notificationUser['id'] == currentUser['id'] or self.hasPerm('admin')):
            raise koji.GenericError('user %s cannot create notifications for user %s' %
                                    (currentUser['name'], notificationUser['name']))

        # sanitize input
        user_id = notificationUser['id']
        if package_id is not None:
            package_id = get_package_id(package_id, strict=True)
        if tag_id is not None:
            tag_id = get_tag_id(tag_id, strict=True)
        success_only = bool(success_only)

        email = '%s@%s' % (notificationUser['name'], context.opts['EmailDomain'])

        # check existing notifications to not have same twice
        for notification in get_build_notifications(user_id):
            if (notification['package_id'] == package_id and
                notification['tag_id'] == tag_id and
                    notification['success_only'] == success_only):
                raise koji.GenericError('notification already exists')

        insert = InsertProcessor('build_notifications')
        insert.set(user_id=user_id, package_id=package_id, tag_id=tag_id,
                   success_only=success_only, email=email)
        insert.execute()

    def deleteNotification(self, id):
        """Delete the notification with the given ID.  If the currently logged-in
        user is not the owner of the notification or an admin, raise a GenericError."""
        notification = self.getBuildNotification(id, strict=True)
        currentUser = self.getLoggedInUser()
        if not currentUser:
            raise koji.GenericError('not logged-in')

        if not (notification['user_id'] == currentUser['id'] or
                self.hasPerm('admin')):
            raise koji.GenericError('user %i cannot delete notifications for user %i' %
                                    (currentUser['id'], notification['user_id']))
        delete = """DELETE FROM build_notifications WHERE id = %(id)i"""
        _dml(delete, locals())

    def createNotificationBlock(self, user_id, package_id=None, tag_id=None):
        """Create notification block. If the user_id does not match the
        currently logged-in user and the currently logged-in user is not an
        admin, raise a GenericError."""
        currentUser = self.getLoggedInUser()
        if not currentUser:
            raise koji.GenericError('not logged in')

        notificationUser = self.getUser(user_id)
        if not notificationUser:
            raise koji.GenericError('invalid user ID: %s' % user_id)

        if not (notificationUser['id'] == currentUser['id'] or self.hasPerm('admin')):
            raise koji.GenericError('user %s cannot create notification blocks for user %s' %
                                    (currentUser['name'], notificationUser['name']))

        # sanitize input
        user_id = notificationUser['id']
        if package_id is not None:
            package_id = get_package_id(package_id, strict=True)
        if tag_id is not None:
            tag_id = get_tag_id(tag_id, strict=True)

        # check existing notifications to not have same twice
        for block in get_build_notification_blocks(user_id):
            if (block['package_id'] == package_id and block['tag_id'] == tag_id):
                raise koji.GenericError('notification already exists')

        insert = InsertProcessor('build_notifications_block')
        insert.set(user_id=user_id, package_id=package_id, tag_id=tag_id)
        insert.execute()

    def deleteNotificationBlock(self, id):
        """Delete the notification block with the given ID.  If the currently logged-in
        user is not the owner of the notification or an admin, raise a GenericError."""
        block = self.getBuildNotificationBlock(id, strict=True)
        currentUser = self.getLoggedInUser()
        if not currentUser:
            raise koji.GenericError('not logged-in')

        if not (block['user_id'] == currentUser['id'] or
                self.hasPerm('admin')):
            raise koji.GenericError('user %i cannot delete notification blocks for user %i' %
                                    (currentUser['id'], block['user_id']))
        delete = """DELETE FROM build_notifications_block WHERE id = %(id)i"""
        _dml(delete, locals())

    def _prepareSearchTerms(self, terms, matchType):
        r"""Process the search terms before passing them to the database.
        If matchType is "glob", "_" will be replaced with "\_" (to match literal
        underscores), "?" will be replaced with "_", and "*" will
        be replaced with "%".  If matchType is "regexp", no changes will be
        made."""
        if matchType == 'glob':
            return terms.replace(
                '\\', '\\\\').replace('_', r'\_').replace('?', '_').replace('*', '%')
        else:
            return terms

    _searchTables = {'package': 'package',
                     'build': 'build',
                     'tag': 'tag',
                     'target': 'build_target',
                     'user': 'users',
                     'host': 'host',
                     'rpm': 'rpminfo',
                     'maven': 'archiveinfo',
                     'win': 'archiveinfo'}

    def search(self, terms, type, matchType, queryOpts=None):
        """Search for an item in the database matching "terms".

        :param str terms: Search for items in the database that match this
                          value.
        :param str type: What object type to search for. Must be one of
                         "package", "build", "tag", "target", "user", "host",
                         "rpm", "maven", or "win".
        :param str matchType: The type of search to perform:
                              - If you specify "glob", Koji will treat "terms"
                                as a case-insensitive glob.
                              - If you specify "regexp", Koji will treat
                                "terms" as a case-insensitive regular
                                expression.
                              - Any other value here will cause to Koji to
                                search for an exact string match for "terms".
        :param dict queryOpts: Options to pass into the database query. Use
                               this to limit or order the results of the
                               search. For example: {'order': 'name'},
                               or {'limit': 5, 'order': '-build_id'}, etc.
        :returns: A list of maps containing "id" and "name".  If no matches
                  are found, this method returns an empty list.
        """
        if not terms:
            raise koji.GenericError('empty search terms')
        if type == 'file':
            # searching by filename is no longer supported
            return _applyQueryOpts([], queryOpts)
        table = self._searchTables.get(type)
        if not table:
            raise koji.GenericError('unknown search type: %s' % type)

        if matchType == 'glob':
            oper = 'ilike'
        elif matchType == 'regexp':
            oper = '~*'
        else:
            oper = '='

        terms = self._prepareSearchTerms(terms, matchType)

        cols = ('id', 'name')
        aliases = cols
        joins = []
        if type == 'build':
            joins.append('package ON build.pkg_id = package.id')
            clause = "package.name || '-' || build.version || '-' || build.release %s %%(terms)s" \
                     % oper
            cols = ('build.id', "package.name || '-' || build.version || '-' || build.release")
        elif type == 'rpm':
            clause = "name || '-' || version || '-' || release || '.' || arch || '.rpm' %s " \
                     "%%(terms)s" % oper
            cols = ('id', "name || '-' || version || '-' || release || '.' || arch || '.rpm'")
        elif type == 'tag':
            joins.append('tag_config ON tag.id = tag_config.tag_id')
            clause = 'tag_config.active = TRUE and name %s %%(terms)s' % oper
        elif type == 'target':
            joins.append('build_target_config '
                         'ON build_target.id = build_target_config.build_target_id')
            clause = 'build_target_config.active = TRUE and name %s %%(terms)s' % oper
        elif type == 'maven':
            cols = ('id', 'filename')
            joins.append('maven_archives ON archiveinfo.id = maven_archives.archive_id')
            clause = "archiveinfo.filename %s %%(terms)s or maven_archives.group_id || '-' || " \
                     "maven_archives.artifact_id || '-' || maven_archives.version %s %%(terms)s" \
                     % (oper, oper)
        elif type == 'win':
            cols = ('id',
                    "trim(leading '/' from win_archives.relpath || '/' || archiveinfo.filename)")
            joins.append('win_archives ON archiveinfo.id = win_archives.archive_id')
            clause = "archiveinfo.filename %s %%(terms)s or win_archives.relpath || '/' || " \
                     "archiveinfo.filename %s %%(terms)s" % (oper, oper)
        else:
            clause = 'name %s %%(terms)s' % oper

        query = QueryProcessor(columns=cols,
                               aliases=aliases, tables=(table,),
                               joins=joins, clauses=(clause,),
                               values=locals(), opts=queryOpts)
        return query.iterate()


class BuildRoot(object):

    def __init__(self, id=None):
        if id is None:
            # db entry has yet to be created
            self.id = None
        else:
            logging.getLogger("koji.hub").debug("BuildRoot id: %s" % id)
            # load buildroot data
            self.load(id)

    def load(self, id):
        fields = [
            'id',
            'br_type',
            'cg_id',
            'cg_version',
            'container_type',
            'container_arch',
            'host_os',
            'host_arch',
            'extra',
        ]
        query = QueryProcessor(columns=fields, tables=['buildroot'],
                               transform=_fix_extra_field,
                               values={'id': id}, clauses=['id=%(id)s'])
        data = query.executeOne()
        if not data:
            raise koji.GenericError('no buildroot with ID: %i' % id)
        self.id = id
        self.data = data
        if data['br_type'] == koji.BR_TYPES['STANDARD']:
            self._load_standard()
        else:
            self.is_standard = False

    def _load_standard(self):
        fields = [
            'host_id',
            'repo_id',
            'task_id',
            'create_event',
            'retire_event',
            'state',
        ]
        query = QueryProcessor(columns=fields, tables=['standard_buildroot'],
                               values={'id': self.id}, clauses=['buildroot_id=%(id)s'])
        data = query.executeOne()
        if not data:
            raise koji.GenericError('Not a standard buildroot: %i' % self.id)
        self.data.update(data)
        # arch for compat
        self.data['arch'] = self.data['container_arch']
        self.is_standard = True

    def new(self, host, repo, arch, task_id=None, ctype='chroot'):
        state = koji.BR_STATES['INIT']
        br_id = _singleValue("SELECT nextval('buildroot_id_seq')", strict=True)
        insert = InsertProcessor('buildroot', data={'id': br_id})
        insert.set(container_arch=arch, container_type=ctype)
        insert.set(br_type=koji.BR_TYPES['STANDARD'])
        insert.execute()
        # and now the other table
        insert = InsertProcessor('standard_buildroot')
        insert.set(buildroot_id=br_id)
        insert.set(host_id=host, repo_id=repo, task_id=task_id, state=state)
        insert.execute()
        self.load(br_id)
        return self.id

    def cg_new(self, data):
        """New content generator buildroot"""

        fields = [
            'br_type',
            'cg_id',
            'cg_version',
            'container_type',
            'container_arch',
            'host_os',
            'host_arch',
            'extra',
        ]
        data.setdefault('br_type', koji.BR_TYPES['EXTERNAL'])
        data = dslice(data, fields)
        for key in fields:
            if key not in data:
                raise koji.GenericError("Buildroot field %s not specified" % key)
        if data['extra'] is not None:
            data['extra'] = json.dumps(data['extra']),
        br_id = _singleValue("SELECT nextval('buildroot_id_seq')", strict=True)
        insert = InsertProcessor('buildroot')
        insert.set(id=br_id, **data)
        insert.execute()
        self.load(br_id)
        return self.id

    def assertStandard(self):
        if self.id is None:
            raise koji.GenericError("buildroot not specified")
        if not self.is_standard:
            raise koji.GenericError('Not a standard buildroot: %s' % self.id)

    def verifyTask(self, task_id):
        self.assertStandard()
        return (task_id == self.data['task_id'])

    def assertTask(self, task_id):
        self.assertStandard()
        if not self.verifyTask(task_id):
            raise koji.ActionNotAllowed('Task %s does not have lock on buildroot %s'
                                        % (task_id, self.id))

    def verifyHost(self, host_id):
        self.assertStandard()
        return (host_id == self.data['host_id'])

    def assertHost(self, host_id):
        self.assertStandard()
        if not self.verifyHost(host_id):
            raise koji.ActionNotAllowed("Host %s not owner of buildroot %s"
                                        % (host_id, self.id))

    def setState(self, state):
        self.assertStandard()
        if isinstance(state, str):
            state = koji.BR_STATES[state]
        # sanity checks
        if state == koji.BR_STATES['INIT']:
            # we do not re-init buildroots
            raise koji.GenericError("Cannot change buildroot state to INIT")
        query = QueryProcessor(columns=['state', 'retire_event'], values=self.data,
                               tables=['standard_buildroot'], clauses=['buildroot_id=%(id)s'],
                               opts={'rowlock': True})
        row = query.executeOne()
        if not row:
            raise koji.GenericError("Unable to get state for buildroot %s" % self.id)
        lstate, retire_event = row
        if koji.BR_STATES[row['state']] == 'EXPIRED':
            # we will quietly ignore a request to expire an expired buildroot
            # otherwise this is an error
            if koji.BR_STATES[state] == 'EXPIRED':
                return
            else:
                raise koji.GenericError("buildroot %i is EXPIRED" % self.id)
        update = UpdateProcessor('standard_buildroot', clauses=['buildroot_id=%(id)s'],
                                 values=self.data)
        update.set(state=state)
        if koji.BR_STATES[state] == 'EXPIRED':
            update.rawset(retire_event='get_event()')
        update.execute()
        self.data['state'] = state

    def getList(self):
        if self.id is None:
            raise koji.GenericError("buildroot not specified")
        brootid = self.id
        fields = (
            ('rpm_id', 'rpm_id'),
            ('is_update', 'is_update'),
            ('rpminfo.name', 'name'),
            ('version', 'version'),
            ('release', 'release'),
            ('epoch', 'epoch'),
            ('arch', 'arch'),
            ('build_id', 'build_id'),
            ('external_repo_id', 'external_repo_id'),
            ('external_repo.name', 'external_repo_name'),
        )
        query = QueryProcessor(columns=[f[0] for f in fields], aliases=[f[1] for f in fields],
                               tables=['buildroot_listing'],
                               joins=["rpminfo ON rpm_id = rpminfo.id",
                                      "external_repo ON external_repo_id = external_repo.id"],
                               clauses=["buildroot_listing.buildroot_id = %(brootid)i"],
                               values=locals())
        return query.execute()

    def _setList(self, rpmlist, update=False):
        """Set or update the list of rpms in a buildroot"""

        update = bool(update)
        if self.id is None:
            raise koji.GenericError("buildroot not specified")
        if update:
            current = set([r['rpm_id'] for r in self.getList()])
        rpm_ids = []
        for an_rpm in rpmlist:
            location = an_rpm.get('location')
            if location:
                data = add_external_rpm(an_rpm, location, strict=False)
                # will add if missing, compare if not
            else:
                data = get_rpm(an_rpm, strict=True)
            rpm_id = data['id']
            if update and rpm_id in current:
                # ignore duplicate packages for updates
                continue
            rpm_ids.append(rpm_id)
        # we sort to try to avoid deadlock issues
        rpm_ids.sort()

        # actually do the inserts (in bulk)
        if rpm_ids:
            insert = BulkInsertProcessor(table='buildroot_listing')
            for rpm_id in rpm_ids:
                insert.add_record(buildroot_id=self.id, rpm_id=rpm_id, is_update=update)
            insert.execute()

    def setList(self, rpmlist):
        """Set the initial list of rpms in a buildroot"""

        if self.is_standard and self.data['state'] != koji.BR_STATES['INIT']:
            raise koji.GenericError("buildroot %(id)s in wrong state %(state)s" % self.data)
        self._setList(rpmlist, update=False)

    def updateList(self, rpmlist):
        """Update the list of packages in a buildroot"""
        if self.is_standard and self.data['state'] != koji.BR_STATES['BUILDING']:
            raise koji.GenericError("buildroot %(id)s in wrong state %(state)s" % self.data)
        self._setList(rpmlist, update=True)

    def getArchiveList(self, queryOpts=None):
        """Get the list of archives in the buildroot"""
        tables = ('archiveinfo',)
        joins = ('buildroot_archives ON archiveinfo.id = buildroot_archives.archive_id',)
        clauses = ('buildroot_archives.buildroot_id = %(id)i',)
        fields = [('id', 'id'),
                  ('type_id', 'type_id'),
                  ('build_id', 'build_id'),
                  ('archiveinfo.buildroot_id', 'buildroot_id'),
                  ('filename', 'filename'),
                  ('size', 'size'),
                  ('checksum', 'checksum'),
                  ('checksum_type', 'checksum_type'),
                  ('project_dep', 'project_dep'),
                  ]
        columns, aliases = zip(*fields)
        query = QueryProcessor(tables=tables, columns=columns,
                               joins=joins, clauses=clauses,
                               values=self.data,
                               opts=queryOpts)
        return query.execute()

    def updateArchiveList(self, archives, project=False):
        """Update the list of archives in a buildroot.

        If project is True, the archives are project dependencies.
        If False, they dependencies required to setup the build environment.
        """

        project = bool(project)
        if self.is_standard:
            if not (context.opts.get('EnableMaven') or context.opts.get('EnableWin')):
                raise koji.GenericError("non-rpm support is not enabled")
            if self.data['state'] != koji.BR_STATES['BUILDING']:
                raise koji.GenericError("buildroot %(id)s in wrong state %(state)s" % self.data)
        archives = set([r['id'] for r in archives])
        current = set([r['id'] for r in self.getArchiveList()])
        new_archives = archives.difference(current)

        if new_archives:
            insert = BulkInsertProcessor('buildroot_archives')
            for archive_id in sorted(new_archives):
                insert.add_record(buildroot_id=self.id,
                                  project_dep=project,
                                  archive_id=archive_id)
            insert.execute()

    def setTools(self, tools):
        """Set tools info for buildroot"""

        if not tools:
            return

        insert = BulkInsertProcessor('buildroot_tools_info')
        for tool in tools:
            insert.add_record(buildroot_id=self.id, tool=tool['name'], version=tool['version'])
        insert.execute()


class Host(object):

    def __init__(self, id=None):
        remote_id = context.session.getHostId()
        if id is None:
            id = remote_id
        if id is None:
            if context.session.logged_in:
                raise koji.AuthError("User %i is not a host" % context.session.user_id)
            else:
                raise koji.AuthError("Not logged in")
        self.id = id
        self.same_host = (id == remote_id)

    def verify(self):
        """Verify that the remote host matches and has the lock"""
        if not self.same_host:
            raise koji.AuthError("Host mismatch")
        if not context.session.exclusive:
            raise koji.AuthError("This method requires an exclusive session")
        return True

    def taskUnwait(self, parent):
        """Clear wait data for task"""
        # unwait the task
        update = UpdateProcessor('task', clauses=['id=%(parent)s'], values=locals())
        update.set(waiting=False)
        update.execute()
        # ...and un-await its subtasks
        update = UpdateProcessor('task', clauses=['parent=%(parent)s'], values=locals())
        update.set(awaited=False)
        update.execute()

    def taskSetWait(self, parent, tasks):
        """Mark task waiting and subtasks awaited"""

        # mark parent as waiting
        update = UpdateProcessor('task', clauses=['id=%(parent)s'], values=locals())
        update.set(waiting=True)
        update.execute()

        # mark children awaited
        if tasks is None:
            # wait on all subtasks
            update = UpdateProcessor('task', clauses=['parent=%(parent)s'], values=locals())
            update.set(awaited=True)
            update.execute()
        elif tasks:
            # wait on specified subtasks
            update = UpdateProcessor('task', clauses=['id IN %(tasks)s', 'parent=%(parent)s'],
                                     values=locals())
            update.set(awaited=True)
            update.execute()
            # clear awaited flag on any other child tasks
            update = UpdateProcessor('task', values=locals(),
                                     clauses=['id NOT IN %(tasks)s',
                                              'parent=%(parent)s',
                                              'awaited=true'])
            update.set(awaited=False)
            update.execute()
        else:
            logger.warning('taskSetWait called on empty task list by parent: %s', parent)

    def taskWaitCheck(self, parent):
        """Return status of awaited subtask

        The return value is [finished, unfinished] where each entry
        is a list of task ids."""
        # check to see if any of the tasks have finished
        c = context.cnx.cursor()
        q = """
        SELECT id,state FROM task
        WHERE parent=%(parent)s AND awaited = TRUE
        FOR UPDATE"""
        c.execute(q, locals())
        canceled = koji.TASK_STATES['CANCELED']
        closed = koji.TASK_STATES['CLOSED']
        failed = koji.TASK_STATES['FAILED']
        finished = []
        unfinished = []
        for id, state in c.fetchall():
            if state in (canceled, closed, failed):
                finished.append(id)
            else:
                unfinished.append(id)
        return finished, unfinished

    def taskWait(self, parent):
        """Return task results or mark tasks as waited upon"""
        finished, unfinished = self.taskWaitCheck(parent)
        # un-await finished tasks
        if finished:
            context.commit_pending = True
            for id in finished:
                c = context.cnx.cursor()
                q = """UPDATE task SET awaited='false' WHERE id=%(id)s"""
                c.execute(q, locals())
        return [finished, unfinished]

    def taskWaitResults(self, parent, tasks, canfail=None):
        if canfail is None:
            canfail = []
        # If we're getting results, we're done waiting
        self.taskUnwait(parent)
        if tasks is None:
            # Query all finished subtasks
            states = tuple([koji.TASK_STATES[s]
                            for s in ['CLOSED', 'FAILED', 'CANCELED']])
            query = QueryProcessor(tables=['task'], columns=['id'],
                                   clauses=['parent=%(parent)s', 'state in %(states)s'],
                                   values=locals(), opts={'asList': True})
            tasks = [r[0] for r in query.execute()]
        # Would use a dict, but xmlrpc requires the keys to be strings
        results = []
        for task_id in tasks:
            task = Task(task_id)
            raise_fault = (task_id not in canfail)
            try:
                results.append([task_id, task.getResult(raise_fault=raise_fault)])
            except koji.GenericError as e:
                # Asking for result of canceled task raises an error
                # For canfail tasks, return error in neutral form
                if not raise_fault and task.isCanceled():
                    f_info = {'faultCode': e.faultCode,
                              'faultString': str(e)}
                    results.append([task_id, f_info])
                    continue
                raise
        return results

    def getHostTasks(self):
        """get status of open tasks assigned to host"""
        c = context.cnx.cursor()
        host_id = self.id
        # query tasks
        fields = ['id', 'waiting', 'weight']
        st_open = koji.TASK_STATES['OPEN']
        q = """
        SELECT %s FROM task
        WHERE host_id = %%(host_id)s AND state = %%(st_open)s
        """ % (",".join(fields))
        c.execute(q, locals())
        tasks = [dict(zip(fields, x)) for x in c.fetchall()]
        for task in tasks:
            id = task['id']
            if task['waiting']:
                finished, unfinished = self.taskWaitCheck(id)
                if finished:
                    task['alert'] = True
        return tasks

    def updateHost(self, task_load, ready):
        host_data = get_host(self.id)
        if task_load != host_data['task_load'] or ready != host_data['ready']:
            c = context.cnx.cursor()
            id = self.id
            q = """UPDATE host SET task_load=%(task_load)s,ready=%(ready)s WHERE id=%(id)s"""
            c.execute(q, locals())
            context.commit_pending = True

    def getLoadData(self):
        """Get load balancing data

        This data is relatively small and the necessary load analysis is
        relatively complex, so we let the host machines crunch it."""
        hosts = get_ready_hosts()
        for host in hosts:
            if host['id'] == self.id:
                break
        else:
            # this host not in ready list
            return [[], []]
        # host is the host making the call
        tasks = get_active_tasks(host)
        return [hosts, tasks]

    def getTask(self):
        """Open next available task and return it"""
        c = context.cnx.cursor()
        id = self.id
        # get arch and channel info for host
        q = """
        SELECT arches FROM host_config WHERE host_id = %(id)s AND active IS TRUE
        """
        c.execute(q, locals())
        arches = c.fetchone()[0].split()
        q = """
        SELECT channel_id FROM host_channels WHERE host_id = %(id)s AND active is TRUE
        """
        c.execute(q, locals())
        channels = [x[0] for x in c.fetchall()]

        # query tasks
        fields = ['id', 'state', 'method', 'request', 'channel_id', 'arch', 'parent']
        st_free = koji.TASK_STATES['FREE']
        st_assigned = koji.TASK_STATES['ASSIGNED']
        q = """
        SELECT %s FROM task
        WHERE (state = %%(st_free)s)
            OR (state = %%(st_assigned)s AND host_id = %%(id)s)
        ORDER BY priority,create_time
        """ % (",".join(fields))
        c.execute(q, locals())
        for data in c.fetchall():
            data = dict(zip(fields, data))
            # XXX - we should do some pruning here, but for now...
            # check arch
            if data['arch'] not in arches:
                continue
            # NOTE: channels ignored for explicit assignments
            if data['state'] != st_assigned and data['channel_id'] not in channels:
                continue
            task = Task(data['id'])
            ret = task.open(self.id)
            if ret is None:
                # someone else got it while we were looking
                # log_error("task %s seems to be locked" % task['id'])
                continue
            return ret
        # else no appropriate tasks
        return None

    def isEnabled(self):
        """Return whether this host is enabled or not."""
        query = """SELECT enabled FROM host_config WHERE host_id = %(id)i AND active IS TRUE"""
        return _singleValue(query, {'id': self.id}, strict=True)


class HostExports(object):
    '''Contains functions that are made available via XMLRPC'''

    def getID(self):
        host = Host()
        host.verify()
        return host.id

    def updateHost(self, task_load, ready):
        host = Host()
        host.verify()
        host.updateHost(task_load, ready)

    def getLoadData(self):
        host = Host()
        host.verify()
        return host.getLoadData()

    def getHost(self):
        """Return information about this host"""
        host = Host()
        host.verify()
        return get_host(host.id)

    def openTask(self, task_id):
        host = Host()
        host.verify()
        task = Task(task_id)
        return task.open(host.id)

    def getTask(self):
        logging.warn("Call host.getTask is deprecated and will be removed in 1.23")
        host = Host()
        host.verify()
        return host.getTask()

    def closeTask(self, task_id, response):
        host = Host()
        host.verify()
        task = Task(task_id)
        task.assertHost(host.id)
        return task.close(response)

    def failTask(self, task_id, response):
        host = Host()
        host.verify()
        task = Task(task_id)
        task.assertHost(host.id)
        return task.fail(response)

    def freeTasks(self, tasks):
        host = Host()
        host.verify()
        for task_id in tasks:
            task = Task(task_id)
            if not task.verifyHost(host.id):
                # it's possible that a task was freed/reassigned since the host
                # last checked, so we should not raise an error
                continue
            task.free()
            # XXX - unfinished
            # remove any files related to task

    def setTaskWeight(self, task_id, weight):
        host = Host()
        host.verify()
        task = Task(task_id)
        task.assertHost(host.id)
        return task.setWeight(weight)

    def getHostTasks(self):
        host = Host()
        host.verify()
        return host.getHostTasks()

    def taskSetWait(self, parent, tasks):
        host = Host()
        host.verify()
        return host.taskSetWait(parent, tasks)

    def taskWait(self, parent):
        host = Host()
        host.verify()
        return host.taskWait(parent)

    def taskWaitResults(self, parent, tasks, canfail=None):
        host = Host()
        host.verify()
        return host.taskWaitResults(parent, tasks, canfail)

    def subtask(self, method, arglist, parent, **opts):
        host = Host()
        host.verify()
        ptask = Task(parent)
        ptask.assertHost(host.id)
        opts['parent'] = parent
        if 'label' in opts:
            # first check for existing task with this parent/label
            q = """SELECT id FROM task
            WHERE parent=%(parent)s AND label=%(label)s"""
            row = _fetchSingle(q, opts)
            if row:
                # return task id
                return row[0]
        if 'kwargs' in opts:
            arglist = koji.encode_args(*arglist, **opts['kwargs'])
            del opts['kwargs']
        return make_task(method, arglist, **opts)

    def subtask2(self, __parent, __taskopts, __method, *args, **opts):
        """A wrapper around subtask with optional signature

        Parameters:
            __parent: task id of the parent task
            __taskopts: dictionary of task options
            __method: the method to be invoked

        Remaining args are passed on to the subtask
        """
        # self.subtask will verify the host
        args = koji.encode_args(*args, **opts)
        return self.subtask(__method, args, __parent, **__taskopts)

    def moveBuildToScratch(self, task_id, srpm, rpms, logs=None):
        "Move a completed scratch build into place (not imported)"
        host = Host()
        host.verify()
        task = Task(task_id)
        task.assertHost(host.id)
        uploadpath = koji.pathinfo.work()
        # verify files exist
        for relpath in [srpm] + rpms:
            fn = "%s/%s" % (uploadpath, relpath)
            if not os.path.exists(fn):
                raise koji.GenericError("no such file: %s" % fn)

        rpms = check_noarch_rpms(uploadpath, rpms, logs=logs)

        # figure out storage location
        #  <scratchdir>/<username>/task_<id>
        scratchdir = koji.pathinfo.scratch()
        username = get_user(task.getOwner())['name']
        dir = "%s/%s/task_%s" % (scratchdir, username, task_id)
        koji.ensuredir(dir)
        for relpath in [srpm] + rpms:
            fn = "%s/%s" % (uploadpath, relpath)
            dest = "%s/%s" % (dir, os.path.basename(fn))
            move_and_symlink(fn, dest)
        if logs:
            for key, files in logs.items():
                if key:
                    logdir = "%s/logs/%s" % (dir, key)
                else:
                    logdir = "%s/logs" % dir
                koji.ensuredir(logdir)
                for relpath in files:
                    fn = "%s/%s" % (uploadpath, relpath)
                    dest = "%s/%s" % (logdir, os.path.basename(fn))
                    move_and_symlink(fn, dest)

    def moveMavenBuildToScratch(self, task_id, results, rpm_results):
        "Move a completed Maven scratch build into place (not imported)"
        if not context.opts.get('EnableMaven'):
            raise koji.GenericError('Maven support not enabled')
        host = Host()
        host.verify()
        task = Task(task_id)
        task.assertHost(host.id)
        scratchdir = koji.pathinfo.scratch()
        username = get_user(task.getOwner())['name']
        destdir = joinpath(scratchdir, username, 'task_%s' % task_id)
        for reldir, files in to_list(results['files'].items()) + [('', results['logs'])]:
            for filename in files:
                if reldir:
                    relpath = joinpath(reldir, filename)
                else:
                    relpath = filename
                src = joinpath(koji.pathinfo.task(results['task_id']), relpath)
                dest = joinpath(destdir, relpath)
                move_and_symlink(src, dest, create_dir=True)
        if rpm_results:
            for relpath in [rpm_results['srpm']] + rpm_results['rpms'] + \
                    rpm_results['logs']:
                src = joinpath(koji.pathinfo.task(rpm_results['task_id']),
                               relpath)
                dest = joinpath(destdir, 'rpms', relpath)
                move_and_symlink(src, dest, create_dir=True)

    def moveWinBuildToScratch(self, task_id, results, rpm_results):
        "Move a completed Windows scratch build into place (not imported)"
        if not context.opts.get('EnableWin'):
            raise koji.GenericError('Windows support not enabled')
        host = Host()
        host.verify()
        task = Task(task_id)
        task.assertHost(host.id)
        scratchdir = koji.pathinfo.scratch()
        username = get_user(task.getOwner())['name']
        destdir = joinpath(scratchdir, username, 'task_%s' % task_id)
        for relpath in to_list(results['output'].keys()) + results['logs']:
            filename = joinpath(koji.pathinfo.task(results['task_id']), relpath)
            dest = joinpath(destdir, relpath)
            move_and_symlink(filename, dest, create_dir=True)
        if rpm_results:
            for relpath in [rpm_results['srpm']] + rpm_results['rpms'] + \
                    rpm_results['logs']:
                filename = joinpath(koji.pathinfo.task(rpm_results['task_id']),
                                    relpath)
                dest = joinpath(destdir, 'rpms', relpath)
                move_and_symlink(filename, dest, create_dir=True)

    def moveImageBuildToScratch(self, task_id, results):
        """move a completed image scratch build into place"""
        host = Host()
        host.verify()
        task = Task(task_id)
        task.assertHost(host.id)
        logger.debug('scratch image results: %s' % results)
        for sub_results in results.values():
            if 'task_id' not in sub_results:
                logger.warning('Task %s failed, no image available' % task_id)
                continue
            workdir = koji.pathinfo.task(sub_results['task_id'])
            scratchdir = koji.pathinfo.scratch()
            username = get_user(task.getOwner())['name']
            destdir = joinpath(scratchdir, username,
                               'task_%s' % sub_results['task_id'])
            for img in sub_results['files'] + sub_results['logs']:
                src = joinpath(workdir, img)
                dest = joinpath(destdir, img)
                logger.debug('renaming %s to %s' % (src, dest))
                move_and_symlink(src, dest, create_dir=True)
            if 'rpmresults' in sub_results:
                rpm_results = sub_results['rpmresults']
                for relpath in [rpm_results['srpm']] + rpm_results['rpms'] + \
                        rpm_results['logs']:
                    src = joinpath(koji.pathinfo.task(
                        rpm_results['task_id']), relpath)
                    dest = joinpath(destdir, 'rpms', relpath)
                    move_and_symlink(src, dest, create_dir=True)

    def initBuild(self, data):
        """Create a stub (rpm) build entry.

        This is done at the very beginning of the build to inform the
        system the build is underway.

        This function is only called for rpm builds, other build types
        have their own init function
        """
        host = Host()
        host.verify()
        # sanity checks
        task = Task(data['task_id'])
        task.assertHost(host.id)
        # prep the data
        data['owner'] = task.getOwner()
        data['state'] = koji.BUILD_STATES['BUILDING']
        data['completion_time'] = None
        build_id = new_build(data)
        binfo = get_build(build_id, strict=True)
        new_typed_build(binfo, 'rpm')
        return build_id

    def completeBuild(self, task_id, build_id, srpm, rpms, brmap=None, logs=None):
        """Import final build contents into the database"""
        # sanity checks
        host = Host()
        host.verify()
        task = Task(task_id)
        task.assertHost(host.id)
        result = import_build(srpm, rpms, brmap, task_id, build_id, logs=logs)
        build_notification(task_id, build_id)
        return result

    def completeImageBuild(self, task_id, build_id, results):
        """Set an image build to the COMPLETE state"""
        host = Host()
        host.verify()
        task = Task(task_id)
        task.assertHost(host.id)

        build_info = get_build(build_id, strict=True)

        # check volume policy
        vol_update = False
        policy_data = {
            'build': build_info,
            'package': build_info['name'],
            'import': True,
            'import_type': 'maven',
        }
        policy_data.update(policy_data_from_task(task_id))
        vol = check_volume_policy(policy_data, strict=False, default='DEFAULT')
        if vol['id'] != build_info['volume_id']:
            build_info['volume_id'] = vol['id']
            build_info['volume_name'] = vol['name']
            vol_update = True

        self.importImage(task_id, build_info, results)
        ensure_volume_symlink(build_info)

        st_old = build_info['state']
        st_complete = koji.BUILD_STATES['COMPLETE']
        koji.plugin.run_callbacks('preBuildStateChange',
                                  attribute='state', old=st_old, new=st_complete, info=build_info)

        update = UpdateProcessor('build', clauses=['id=%(build_id)i'],
                                 values={'build_id': build_id})
        update.set(id=build_id, state=st_complete)
        update.rawset(completion_time='now()')
        if vol_update:
            update.set(volume_id=build_info['volume_id'])
        update.execute()
        build_info = get_build(build_id, strict=True)
        koji.plugin.run_callbacks('postBuildStateChange',
                                  attribute='state', old=st_old, new=st_complete, info=build_info)

        # send email
        build_notification(task_id, build_id)

    def initMavenBuild(self, task_id, build_info, maven_info):
        """Create a new in-progress Maven build
           Synthesize the release number by taking the (integer) release of the
           last successful build and incrementing it."""
        if not context.opts.get('EnableMaven'):
            raise koji.GenericError("Maven support not enabled")
        host = Host()
        host.verify()
        task = Task(task_id)
        task.assertHost(host.id)
        build_info['release'] = get_next_release(build_info)
        data = build_info.copy()
        data['task_id'] = task_id
        data['owner'] = task.getOwner()
        data['state'] = koji.BUILD_STATES['BUILDING']
        data['completion_time'] = None
        build_id = new_build(data)
        data['id'] = build_id
        new_maven_build(data, maven_info)

        return data

    def createMavenBuild(self, build_info, maven_info):
        """
        Associate Maven metadata with an existing build.  Used
        by the rpm2maven plugin.
        """
        host = Host()
        host.verify()
        if not context.opts.get('EnableMaven'):
            raise koji.GenericError("Maven support not enabled")
        new_maven_build(build_info, maven_info)

    def completeMavenBuild(self, task_id, build_id, maven_results, rpm_results):
        """Complete the Maven build."""
        if not context.opts.get('EnableMaven'):
            raise koji.GenericError("Maven support not enabled")
        host = Host()
        host.verify()
        task = Task(task_id)
        task.assertHost(host.id)

        build_info = get_build(build_id, strict=True)
        maven_info = get_maven_build(build_id, strict=True)

        # check volume policy
        vol_update = False
        policy_data = {
            'build': build_info,
            'package': build_info['name'],
            'import': True,
            'import_type': 'maven',
        }
        policy_data.update(policy_data_from_task(task_id))
        vol = check_volume_policy(policy_data, strict=False, default='DEFAULT')
        if vol['id'] != build_info['volume_id']:
            build_info['volume_id'] = vol['id']
            build_info['volume_name'] = vol['name']
            vol_update = True

        # import the build output
        maven_task_id = maven_results['task_id']
        maven_buildroot_id = maven_results['buildroot_id']
        maven_task_dir = koji.pathinfo.task(maven_task_id)
        for relpath, files in maven_results['files'].items():
            dir_maven_info = maven_info
            poms = [f for f in files if f.endswith('.pom')]
            if len(poms) == 0:
                pass
            elif len(poms) == 1:
                # This directory has a .pom file, so get the Maven group_id,
                # artifact_id, and version from it and associate those with
                # the artifacts in this directory
                pom_path = joinpath(maven_task_dir, relpath, poms[0])
                pom_info = koji.parse_pom(pom_path)
                dir_maven_info = koji.pom_to_maven_info(pom_info)
            else:
                raise koji.BuildError('multiple .pom files in %s: %s' % (relpath, ', '.join(poms)))

            for filename in files:
                if os.path.splitext(filename)[1] in ('.md5', '.sha1'):
                    # metadata, we'll recreate that ourselves
                    continue
                filepath = joinpath(maven_task_dir, relpath, filename)
                if filename == 'maven-metadata.xml':
                    # We want the maven-metadata.xml to be present in the build dir
                    # so that it's a valid Maven repo, but we don't want to track it
                    # in the database because we regenerate it when creating tag repos.
                    # So we special-case it here.
                    destdir = joinpath(koji.pathinfo.mavenbuild(build_info),
                                       relpath)
                    _import_archive_file(filepath, destdir)
                    _generate_maven_metadata(destdir)
                    continue
                archivetype = get_archive_type(filename)
                if not archivetype:
                    # Unknown archive type, fail the build
                    raise koji.BuildError('unsupported file type: %s' % filename)
                import_archive(filepath, build_info, 'maven', dir_maven_info, maven_buildroot_id)

        # move the logs to their final destination
        for log_path in maven_results['logs']:
            import_build_log(joinpath(maven_task_dir, log_path),
                             build_info, subdir='maven')

        if rpm_results:
            _import_wrapper(rpm_results['task_id'], build_info, rpm_results)

        ensure_volume_symlink(build_info)

        # update build state
        st_complete = koji.BUILD_STATES['COMPLETE']
        st_old = build_info['state']
        koji.plugin.run_callbacks('preBuildStateChange',
                                  attribute='state', old=st_old, new=st_complete, info=build_info)
        update = UpdateProcessor('build', clauses=['id=%(build_id)i'],
                                 values={'build_id': build_id})
        update.set(state=st_complete)
        if vol_update:
            update.set(volume_id=build_info['volume_id'])
        update.rawset(completion_time='now()')
        update.execute()
        build_info = get_build(build_id, strict=True)
        koji.plugin.run_callbacks('postBuildStateChange',
                                  attribute='state', old=st_old, new=st_complete, info=build_info)

        # send email
        build_notification(task_id, build_id)

    def importArchive(self, filepath, buildinfo, type, typeInfo):
        """
        Import an archive file and associate it with a build.  The archive can
        be any non-rpm filetype supported by Koji.  Used by the rpm2maven plugin.
        """
        host = Host()
        host.verify()
        if type == 'maven':
            if not context.opts.get('EnableMaven'):
                raise koji.GenericError('Maven support not enabled')
        elif type == 'win':
            if not context.opts.get('EnableWin'):
                raise koji.GenericError('Windows support not enabled')
        else:
            raise koji.GenericError('unsupported archive type: %s' % type)
        import_archive(filepath, buildinfo, type, typeInfo)

    def importWrapperRPMs(self, task_id, build_id, rpm_results):
        """Import the wrapper rpms and associate them with the given build.  The build
        must not have any existing rpms associated with it."""
        if not context.opts.get('EnableMaven'):
            raise koji.GenericError("Maven support not enabled")
        host = Host()
        host.verify()
        task = Task(task_id)
        task.assertHost(host.id)

        build_info = get_build(build_id, strict=True)

        if build_info['state'] != koji.BUILD_STATES['COMPLETE']:
            raise koji.GenericError(
                'cannot import wrapper rpms for %s: build state is %s, not complete' %
                (koji.buildLabel(build_info), koji.BUILD_STATES[build_info['state']].lower()))

        if list_rpms(buildID=build_info['id']):
            # don't allow overwriting of already-imported wrapper RPMs
            raise koji.GenericError('wrapper rpms for %s have already been imported' %
                                    koji.buildLabel(build_info))

        _import_wrapper(task.id, build_info, rpm_results)

    def initImageBuild(self, task_id, build_info):
        """create a new in-progress image build"""
        host = Host()
        host.verify()
        task = Task(task_id)
        task.assertHost(host.id)
        data = build_info.copy()
        data['task_id'] = task_id
        data['owner'] = task.getOwner()
        data['state'] = koji.BUILD_STATES['BUILDING']
        data['completion_time'] = None
        if data.get('release') is None:
            data['release'] = get_next_release(build_info)
        build_id = new_build(data)
        data['id'] = build_id
        new_image_build(data)
        return data

    def initWinBuild(self, task_id, build_info, win_info):
        """
        Create a new in-progress Windows build.
        """
        if not context.opts.get('EnableWin'):
            raise koji.GenericError('Windows support not enabled')
        host = Host()
        host.verify()
        # sanity checks
        task = Task(task_id)
        task.assertHost(host.id)
        # build_info must contain name, version, and release
        data = build_info.copy()
        data['task_id'] = task_id
        data['owner'] = task.getOwner()
        data['state'] = koji.BUILD_STATES['BUILDING']
        data['completion_time'] = None
        build_id = new_build(data)
        data['id'] = build_id
        new_win_build(data, win_info)
        return data

    def completeWinBuild(self, task_id, build_id, results, rpm_results):
        """Complete a Windows build"""
        if not context.opts.get('EnableWin'):
            raise koji.GenericError('Windows support not enabled')
        host = Host()
        host.verify()
        task = Task(task_id)
        task.assertHost(host.id)

        build_info = get_build(build_id, strict=True)
        get_win_build(build_id, strict=True)  # raise exception if not found.

        # check volume policy
        vol_update = False
        policy_data = {
            'build': build_info,
            'package': build_info['name'],
            'import': True,
            'import_type': 'win',
        }
        policy_data.update(policy_data_from_task(task_id))
        vol = check_volume_policy(policy_data, strict=False, default='DEFAULT')
        if vol['id'] != build_info['volume_id']:
            build_info['volume_id'] = vol['id']
            build_info['volume_name'] = vol['name']
            vol_update = True

        task_dir = koji.pathinfo.task(results['task_id'])
        # import the build output
        for relpath, metadata in results['output'].items():
            archivetype = get_archive_type(relpath)
            if not archivetype:
                # Unknown archive type, fail the build
                raise koji.BuildError('unsupported file type: %s' % relpath)
            filepath = joinpath(task_dir, relpath)
            metadata['relpath'] = os.path.dirname(relpath)
            import_archive(filepath, build_info, 'win', metadata,
                           buildroot_id=results['buildroot_id'])

        # move the logs to their final destination
        for relpath in results['logs']:
            subdir = 'win'
            reldir = os.path.dirname(relpath)
            if reldir:
                subdir = joinpath(subdir, reldir)
            import_build_log(joinpath(task_dir, relpath),
                             build_info, subdir=subdir)

        if rpm_results:
            _import_wrapper(rpm_results['task_id'], build_info, rpm_results)

        ensure_volume_symlink(build_info)

        # update build state
        st_old = build_info['state']
        st_complete = koji.BUILD_STATES['COMPLETE']
        koji.plugin.run_callbacks('preBuildStateChange',
                                  attribute='state', old=st_old, new=st_complete, info=build_info)
        update = UpdateProcessor('build', clauses=['id=%(build_id)i'],
                                 values={'build_id': build_id})
        update.set(state=st_complete)
        if vol_update:
            update.set(volume_id=build_info['volume_id'])
        update.rawset(completion_time='now()')
        update.execute()
        build_info = get_build(build_id, strict=True)
        koji.plugin.run_callbacks('postBuildStateChange',
                                  attribute='state', old=st_old, new=st_complete, info=build_info)

        # send email
        build_notification(task_id, build_id)

    def failBuild(self, task_id, build_id):
        """Mark the build as failed.  If the current state is not
        'BUILDING', or the current completion_time is not null, a
        GenericError will be raised."""
        host = Host()
        host.verify()
        task = Task(task_id)
        task.assertHost(host.id)

        st_failed = koji.BUILD_STATES['FAILED']
        buildinfo = get_build(build_id, strict=True)
        st_old = buildinfo['state']
        koji.plugin.run_callbacks('preBuildStateChange',
                                  attribute='state', old=st_old, new=st_failed, info=buildinfo)

        query = """SELECT state, completion_time
        FROM build
        WHERE id = %(build_id)i
        FOR UPDATE"""
        result = _singleRow(query, locals(), ('state', 'completion_time'))

        if result['state'] != koji.BUILD_STATES['BUILDING']:
            raise koji.GenericError('cannot update build %i, state: %s' %
                                    (build_id, koji.BUILD_STATES[result['state']]))
        elif result['completion_time'] is not None:
            raise koji.GenericError('cannot update build %i, completed at %s' %
                                    (build_id, result['completion_time']))

        update = """UPDATE build
        SET state = %(st_failed)i,
        completion_time = NOW()
        WHERE id = %(build_id)i"""
        _dml(update, locals())
        buildinfo = get_build(build_id, strict=True)
        koji.plugin.run_callbacks('postBuildStateChange',
                                  attribute='state', old=st_old, new=st_failed, info=buildinfo)
        build_notification(task_id, build_id)

    def tagBuild(self, task_id, tag, build, force=False, fromtag=None):
        """Tag a build (host version)

        This tags as the user who owns the task

        If fromtag is specified, also untag the package (i.e. move in a single
        transaction)

        No return value
        """
        host = Host()
        host.verify()
        task = Task(task_id)
        task.assertHost(host.id)
        build = get_build(build, strict=True)
        pkg_id = build['package_id']
        tag_id = get_tag(tag, strict=True)['id']
        user_id = task.getOwner()
        policy_data = {'tag': tag, 'build': build, 'fromtag': fromtag}
        policy_data['user_id'] = user_id
        if fromtag is None:
            policy_data['operation'] = 'tag'
        else:
            policy_data['operation'] = 'move'
        # don't check policy for admins using force
        assert_policy('tag', policy_data, force=force)
        # package list check
        pkgs = readPackageList(tagID=tag_id, pkgID=pkg_id, inherit=True)
        pkg_error = None
        if pkg_id not in pkgs:
            pkg_error = "Package %s not in list for %s" % (build['name'], tag)
        elif pkgs[pkg_id]['blocked']:
            pkg_error = "Package %s blocked in %s" % (build['name'], tag)
        if pkg_error:
            if force and context.session.hasPerm('admin'):
                pkglist_add(tag_id, pkg_id, force=True, block=False)
                logger.info("Package added %s/%s by %s by force" % (
                    tag, build['nvr'], context.session.user_data['name']))
            else:
                raise koji.TagError(pkg_error)
        # do the actual work now
        if fromtag:
            _untag_build(fromtag, build, user_id=user_id, force=force, strict=True)
        _tag_build(tag, build, user_id=user_id, force=force)

    def importImage(self, task_id, build_info, results):
        """
        Import a built image, populating the database with metadata and
        moving the image to its final location.
        """
        for sub_results in results.values():
            if 'task_id' not in sub_results:
                logger.warning('Task %s failed, no image available' % task_id)
                continue
            importImageInternal(task_id, build_info, sub_results)
            if 'rpmresults' in sub_results:
                rpm_results = sub_results['rpmresults']
                _import_wrapper(rpm_results['task_id'],
                                get_build(build_info['id'], strict=True), rpm_results)

    def tagNotification(self, is_successful, tag_id, from_id, build_id, user_id,
                        ignore_success=False, failure_msg=''):
        """Create a tag notification message.
        Handles creation of tagNotification tasks for hosts."""
        host = Host()
        host.verify()
        tag_notification(is_successful, tag_id, from_id, build_id, user_id, ignore_success,
                         failure_msg)

    def checkPolicy(self, name, data, default='deny', strict=False):
        host = Host()
        host.verify()
        return check_policy(name, data, default=default, strict=strict)

    def assertPolicy(self, name, data, default='deny'):
        host = Host()
        host.verify()
        check_policy(name, data, default=default, strict=True)

    def evalPolicy(self, name, data):
        """Evaluate named policy with given data and return the result"""
        host = Host()
        host.verify()
        ruleset = context.policy.get(name)
        if not ruleset:
            raise koji.GenericError("no such policy: %s" % name)
        return ruleset.apply(data)

    def newBuildRoot(self, repo, arch, task_id=None):
        host = Host()
        host.verify()
        if task_id is not None:
            Task(task_id).assertHost(host.id)
        br = BuildRoot()
        return br.new(host.id, repo, arch, task_id=task_id)

    def setBuildRootState(self, brootid, state, task_id=None):
        host = Host()
        host.verify()
        if task_id is not None:
            Task(task_id).assertHost(host.id)
        br = BuildRoot(brootid)
        br.assertHost(host.id)
        if task_id is not None:
            br.assertTask(task_id)
        return br.setState(state)

    def setBuildRootList(self, brootid, rpmlist, task_id=None):
        host = Host()
        host.verify()
        if task_id is not None:
            Task(task_id).assertHost(host.id)
        br = BuildRoot(brootid)
        br.assertHost(host.id)
        if task_id is not None:
            br.assertTask(task_id)
        return br.setList(rpmlist)

    def updateBuildRootList(self, brootid, rpmlist, task_id=None):
        host = Host()
        host.verify()
        if task_id is not None:
            Task(task_id).assertHost(host.id)
        br = BuildRoot(brootid)
        br.assertHost(host.id)
        if task_id is not None:
            br.assertTask(task_id)
        return br.updateList(rpmlist)

    def updateBuildrootArchives(self, brootid, task_id, archives, project=False):
        host = Host()
        host.verify()
        Task(task_id).assertHost(host.id)
        br = BuildRoot(brootid)
        br.assertHost(host.id)
        br.assertTask(task_id)
        return br.updateArchiveList(archives, project)

    def updateMavenBuildRootList(self, brootid, task_id, mavenlist, ignore=None, project=False,
                                 ignore_unknown=False, extra_deps=None):
        if not context.opts.get('EnableMaven'):
            raise koji.GenericError("Maven support not enabled")
        host = Host()
        host.verify()
        Task(task_id).assertHost(host.id)
        br = BuildRoot(brootid)
        br.assertHost(host.id)
        br.assertTask(task_id)

        repo = repo_info(br.data['repo_id'], strict=True)
        tag = get_tag(repo['tag_id'], strict=True)
        maven_build_index = {}
        # Index the maven_tag_archives result by group_id:artifact_id:version
        # The function ensures that each g:a:v maps to a single build id.
        # The generator returned by maven_tag_archives can create a lot of data,
        # but this index will only consume a fraction of that.
        for archive in maven_tag_archives(tag['id'], event_id=repo['create_event']):
            # unfortunately pgdb does not appear to intern strings, but still
            # better not to create any new ones
            idx_build = \
                maven_build_index.setdefault(
                    archive['group_id'], {}).setdefault(
                        archive['artifact_id'], {}).setdefault(
                            archive['version'], archive['build_id'])
            if idx_build != archive['build_id']:
                logger.error(
                    "Found multiple builds for %(group_id)s:%(artifact_id)s:%(version)s. "
                    "Current build: %(build_id)i", archive)
                logger.error("Indexed build id was %i", idx_build)

        if not ignore:
            ignore = []
        if not extra_deps:
            extra_deps = []
        task_deps = {}
        for dep in extra_deps:
            if isinstance(dep, int):
                task_output = list_task_output(dep, stat=True)
                for filepath, filestats in task_output.items():
                    if os.path.splitext(filepath)[1] in ['.log', '.md5', '.sha1']:
                        continue
                    tokens = filepath.split('/')
                    if len(tokens) < 4:
                        # should never happen in a Maven repo
                        continue
                    filename = tokens.pop()
                    maven_info = {}
                    maven_info['version'] = tokens.pop()
                    maven_info['artifact_id'] = tokens.pop()
                    maven_info['group_id'] = '.'.join(tokens)
                    maven_label = koji.mavenLabel(maven_info)
                    fileinfo = {'filename': filename,
                                'size': int(filestats['st_size'])}
                    if maven_label in task_deps:
                        task_deps[maven_label]['files'].append(fileinfo)
                    else:
                        task_deps[maven_label] = {'maven_info': maven_info,
                                                  'files': [fileinfo]}
            else:
                build = get_build(dep, strict=True)
                for archive in list_archives(buildID=build['id'], type='maven'):
                    idx_build = \
                        maven_build_index.setdefault(
                            archive['group_id'], {}).setdefault(
                                archive['artifact_id'], {}).setdefault(
                                    archive['version'], archive['build_id'])
                    if idx_build != archive['build_id']:
                        logger.error(
                            "Overriding build for %(group_id)s:%(artifact_id)s:%(version)s.",
                            archive)
                        logger.error(
                            "Current build is %s, new build is %s.",
                            idx_build, archive['build_id'])
                        maven_build_index[
                            archive['group_id']
                        ][
                            archive['artifact_id']
                        ][
                            archive['version']
                        ] = archive['build_id']

        ignore.extend(task_deps.values())

        SNAPSHOT_RE = re.compile(r'-\d{8}\.\d{6}-\d+')
        ignore_by_label = {}
        for entry in ignore:
            ignore_info = entry['maven_info']
            ignore_label = koji.mavenLabel(ignore_info)
            if ignore_label not in ignore_by_label:
                ignore_by_label[ignore_label] = {}
            for fileinfo in entry['files']:
                filename = fileinfo['filename']
                ignore_by_label[ignore_label][filename] = fileinfo
                if SNAPSHOT_RE.search(filename):
                    # the task output snapshot versions, which means the
                    # local repo will contain the same file with both
                    # -SNAPSHOT and -{timestamp} in the name
                    snapname = SNAPSHOT_RE.sub('-SNAPSHOT', filename)
                    ignore_by_label[ignore_label][snapname] = fileinfo

        archives = []
        for entry in mavenlist:
            maven_info = entry['maven_info']
            maven_label = koji.mavenLabel(maven_info)
            ignore_archives = ignore_by_label.get(maven_label, {})
            build_id = maven_build_index.get(
                maven_info['group_id'], {}).get(
                maven_info['artifact_id'], {}).get(
                maven_info['version'])
            if not build_id:
                if not ignore_unknown:
                    # just warn for now. might be in ignore list. the loop below will check.
                    logger.warning('Unmatched maven g:a:v in build environment: '
                                   '%(group_id)s:%(artifact_id)s:%(version)s', maven_info)
                build_archives = {}
            else:
                tinfo = dslice(maven_info, ['group_id', 'artifact_id', 'version'])
                build_archives = list_archives(buildID=build_id, type='maven', typeInfo=tinfo)
                # index by filename
                build_archives = dict([(a['filename'], a) for a in build_archives])

            for fileinfo in entry['files']:
                ignore_archive = ignore_archives.get(fileinfo['filename'])
                tag_archive = build_archives.get(fileinfo['filename'])
                if tag_archive and fileinfo['size'] == tag_archive['size']:
                    archives.append(tag_archive)
                elif ignore_archive and fileinfo['size'] == ignore_archive['size']:
                    pass
                else:
                    if not ignore_unknown:
                        logger.error("Unknown file for %(group_id)s:%(artifact_id)s:%(version)s",
                                     maven_info)
                        if build_id:
                            build = get_build(build_id)
                            logger.error("g:a:v supplied by build %(nvr)s", build)
                            logger.error("Build supplies %i archives: %r",
                                         len(build_archives), to_list(build_archives.keys()))
                        if tag_archive:
                            logger.error("Size mismatch, br: %i, db: %i",
                                         fileinfo['size'], tag_archive['size'])
                        raise koji.BuildrootError(
                            'Unknown file in build environment: %s, size: %s' %
                            ('%s/%s' % (fileinfo['path'], fileinfo['filename']), fileinfo['size']))

        return br.updateArchiveList(archives, project)

    def repoInit(self, tag, with_src=False, with_debuginfo=False, event=None,
                 with_separate_src=False):
        """Initialize a new repo for tag"""
        host = Host()
        host.verify()
        return repo_init(tag, with_src=with_src, with_debuginfo=with_debuginfo, event=event,
                         with_separate_src=with_separate_src)

    def repoDone(self, repo_id, data, expire=False):
        """Finalize a repo

        repo_id: the id of the repo
        data: a dictionary of repo files in the form:
              { arch: [uploadpath, [file1, file2, ...]], ...}
        expire: if set to true, mark the repo expired immediately [*]

        Actions:
        * Move uploaded repo files into place
        * Mark repo ready
        * Expire earlier repos
        * Move/create 'latest' symlink

        For dist repos, the move step is skipped (that is handled in
        distRepoMove).

        * This is used when a repo from an older event is generated
        """
        host = Host()
        host.verify()
        rinfo = repo_info(repo_id, strict=True)
        koji.plugin.run_callbacks('preRepoDone', repo=rinfo, data=data, expire=expire)
        if rinfo['state'] != koji.REPO_INIT:
            raise koji.GenericError("Repo %(id)s not in INIT state (got %(state)s)" % rinfo)
        repodir = koji.pathinfo.repo(repo_id, rinfo['tag_name'])
        workdir = koji.pathinfo.work()
        if not rinfo['dist']:
            for arch, (uploadpath, files) in data.items():
                archdir = "%s/%s" % (repodir, koji.canonArch(arch))
                if not os.path.isdir(archdir):
                    raise koji.GenericError("Repo arch directory missing: %s" % archdir)
                datadir = "%s/repodata" % archdir
                koji.ensuredir(datadir)
                for fn in files:
                    src = "%s/%s/%s" % (workdir, uploadpath, fn)
                    if fn.endswith('pkglist'):
                        dst = '%s/%s' % (archdir, fn)
                    else:
                        dst = "%s/%s" % (datadir, fn)
                    if not os.path.exists(src):
                        raise koji.GenericError("uploaded file missing: %s" % src)
                    safer_move(src, dst)
        if expire:
            repo_expire(repo_id)
            koji.plugin.run_callbacks('postRepoDone', repo=rinfo, data=data, expire=expire)
            return
        # else:
        repo_ready(repo_id)
        repo_expire_older(rinfo['tag_id'], rinfo['create_event'], rinfo['dist'])

        # make a latest link
        if rinfo['dist']:
            latestrepolink = koji.pathinfo.distrepo('latest', rinfo['tag_name'])
        else:
            latestrepolink = koji.pathinfo.repo('latest', rinfo['tag_name'])
            # XXX - this is a slight abuse of pathinfo
        try:
            if os.path.lexists(latestrepolink):
                os.unlink(latestrepolink)
            os.symlink(str(repo_id), latestrepolink)
        except OSError:
            # making this link is nonessential
            log_error("Unable to create latest link for repo: %s" % repodir)
        koji.plugin.run_callbacks('postRepoDone', repo=rinfo, data=data, expire=expire)

    def distRepoMove(self, repo_id, uploadpath, arch):
        """
        Move one arch of a dist repo into its final location

        Unlike normal repos, dist repos have all their content linked (or
        copied) into place.

        repo_id - the repo to move
        uploadpath - where the uploaded files are
        arch - the arch of the repo

        uploadpath should contain a repo_manifest file

        The uploaded files should include:
            - kojipkgs: json file with information about the component rpms
            - repo metadata files
        """
        host = Host()
        host.verify()
        workdir = koji.pathinfo.work()
        rinfo = repo_info(repo_id, strict=True)
        repodir = koji.pathinfo.distrepo(repo_id, rinfo['tag_name'])
        # Note: if repo is on a different volume then repodir should be a
        #   valid symlink and this function should still do the right thing
        archdir = "%s/%s" % (repodir, koji.canonArch(arch))
        if not os.path.isdir(archdir):
            raise koji.GenericError("Repo arch directory missing: %s" % archdir)
        repo_state = koji.REPO_STATES[rinfo['state']]
        if repo_state != 'INIT':
            raise koji.GenericError('Repo is in state: %s' % repo_state)

        # read manifest
        fn = '%s/%s/repo_manifest' % (workdir, uploadpath)
        if not os.path.isfile(fn):
            raise koji.GenericError('Missing repo manifest')
        with open(fn) as fp:
            files = json.load(fp)

        # Read package data
        fn = '%s/%s/kojipkgs' % (workdir, uploadpath)
        if not os.path.isfile(fn):
            raise koji.GenericError('Missing kojipkgs file')
        with open(fn) as fp:
            kojipkgs = json.load(fp)

        # Figure out where to send the uploaded files
        file_moves = []
        for relpath in files:
            src = "%s/%s/%s" % (workdir, uploadpath, relpath)
            dst = "%s/%s" % (archdir, relpath)
            if not os.path.exists(src):
                raise koji.GenericError("uploaded file missing: %s" % src)
            file_moves.append([src, dst])

        # get rpms
        build_dirs = {}
        rpmdata = {}
        rpm_check_keys = ['name', 'version', 'release', 'arch', 'epoch',
                          'size', 'payloadhash', 'build_id']
        for bnp in kojipkgs:
            rpminfo = kojipkgs[bnp]
            rpm_id = rpminfo['id']
            sigkey = rpminfo['sigkey']
            _rpminfo = get_rpm(rpm_id, strict=True)
            for key in rpm_check_keys:
                if key not in rpminfo or rpminfo[key] != _rpminfo[key]:
                    raise koji.GenericError(
                        'kojipkgs entry does not match db: file %s, key %s'
                        % (bnp, key))
            if sigkey is None or sigkey == '':
                relpath = koji.pathinfo.rpm(rpminfo)
            else:
                relpath = koji.pathinfo.signed(rpminfo, sigkey)
            rpminfo['_relpath'] = relpath
            if rpminfo['build_id'] in build_dirs:
                builddir = build_dirs[rpminfo['build_id']]
            else:
                binfo = get_build(rpminfo['build_id'])
                builddir = koji.pathinfo.build(binfo)
                build_dirs[rpminfo['build_id']] = builddir
            rpminfo['_fullpath'] = joinpath(builddir, relpath)
            rpmdata[bnp] = rpminfo

        # move the uploaded files
        dirnames = set([os.path.dirname(fm[1]) for fm in file_moves])
        for dirname in dirnames:
            koji.ensuredir(dirname)
        for src, dst in file_moves:
            safer_move(src, dst)

        # hardlink or copy the rpms into the final repodir
        # TODO: properly consider split-volume functionality
        for fn in rpmdata:
            rpminfo = rpmdata[fn]
            rpmpath = rpminfo['_fullpath']
            bnp = fn
            bnplet = bnp[0].lower()
            ddir = joinpath(archdir, 'Packages', bnplet)
            koji.ensuredir(ddir)
            l_dst = joinpath(ddir, bnp)
            if os.path.exists(l_dst):
                raise koji.GenericError("File already in repo: %s", l_dst)
            logger.debug("os.link(%r, %r)", rpmpath, l_dst)
            try:
                os.link(rpmpath, l_dst)
            except OSError as ose:
                if ose.errno == 18:
                    shutil.copy2(rpmpath, l_dst)
                else:
                    raise

    def isEnabled(self):
        host = Host()
        host.verify()
        return host.isEnabled()


def get_upload_path(reldir, name, create=False, volume=None):
    orig_reldir = reldir
    orig_name = name
    # lots of sanity checks
    d, name = os.path.split(name)
    if d or name.startswith('.'):
        raise koji.GenericError("Invalid upload filename: %s" % orig_name)
    reldir = os.path.normpath(reldir)
    if not reldir or reldir.startswith('..'):
        raise koji.GenericError("Invalid upload directory: %s" % orig_reldir)
    if volume is not None:
        # make sure the volume is valid
        lookup_name('volume', volume, strict=True)
    parts = reldir.split('/')
    check_user = True
    if create and parts[0] == "tasks":
        if len(parts) < 3:
            raise koji.GenericError("Invalid task upload directory: %s" % orig_reldir)
        try:
            task_id = int(parts[2])
        except ValueError:
            raise koji.GenericError("Invalid task upload directory: %s" % orig_reldir)
        # only the host running this task may write here
        host = Host()
        host.verify()
        Task(task_id).assertHost(host.id)
        check_user = False
    udir = joinpath(koji.pathinfo.work(volume=volume), reldir)
    if create:
        koji.ensuredir(udir)
        if check_user:
            # assuming login was asserted earlier
            u_fn = joinpath(udir, '.user')
            if os.path.exists(u_fn):
                user_id = int(open(u_fn, 'r').read())
                if context.session.user_id != user_id:
                    raise koji.GenericError("Invalid upload directory, not owner: %s" %
                                            orig_reldir)
            else:
                with open(u_fn, 'w') as fo:
                    fo.write(str(context.session.user_id))
    return joinpath(udir, name)


def get_verify_class(verify):
    if verify == 'md5':
        return md5_constructor
    elif verify == 'adler32':
        return koji.util.adler32_constructor
    elif verify == 'sha256':
        return hashlib.sha256
    elif verify:
        raise koji.GenericError("Unsupported verify type: %s" % verify)
    else:
        return None


def handle_upload(environ):
    """Handle file upload via POST request"""
    logger = logging.getLogger('koji.upload')
    start = time.time()
    if not context.session.logged_in:
        raise koji.ActionNotAllowed('you must be logged-in to upload a file')
    args = parse_qs(environ.get('QUERY_STRING', ''), strict_parsing=True)
    # XXX - already parsed by auth
    name = args['filename'][0]
    path = args.get('filepath', ('',))[0]
    verify = args.get('fileverify', ('',))[0]
    overwrite = args.get('overwrite', ('',))[0]
    offset = args.get('offset', ('0',))[0]
    offset = int(offset)
    volume = args.get('volume', ('DEFAULT',))[0]
    fn = get_upload_path(path, name, create=True, volume=volume)
    if os.path.exists(fn):
        if not os.path.isfile(fn):
            raise koji.GenericError("destination not a file: %s" % fn)
        if offset == 0 and not overwrite:
            raise koji.GenericError("upload path exists: %s" % fn)
    chksum = get_verify_class(verify)()
    size = 0
    inf = environ['wsgi.input']
    fd = os.open(fn, os.O_RDWR | os.O_CREAT, 0o666)
    try:
        try:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError as e:
            raise koji.LockError(e)
        if offset == -1:
            offset = os.lseek(fd, 0, 2)
        else:
            os.ftruncate(fd, offset)
            os.lseek(fd, offset, 0)
        while True:
            chunk = inf.read(65536)
            if not chunk:
                break
            size += len(chunk)
            if verify:
                chksum.update(chunk)
            os.write(fd, chunk)
    finally:
        # this will also remove our lock
        os.close(fd)
    ret = {
        'size': size,
        'fileverify': verify,
        'offset': offset,
    }
    if verify:
        # unsigned 32bit - could be too big for xmlrpc
        ret['hexdigest'] = chksum.hexdigest()
    logger.debug("Upload result: %r", ret)
    logger.info("Completed upload for session %s (#%s): %f seconds, %i bytes, %s",
                context.session.id, context.session.callnum,
                time.time() - start, size, fn)
    return ret
