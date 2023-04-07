# Task related hub code
import base64
import logging
import time
import xmlrpc.client

import koji
from .db import QueryProcessor, UpdateProcessor
from .util import convert_value
from koji.context import context
from koji.util import decode_bytes


logger = logging.getLogger('koji.hub.task')


class Task(object):
    """A task for the build hosts"""

    fields = (
        ('task.id', 'id'),
        ('task.state', 'state'),
        ('task.create_time', 'create_time'),
        ("date_part('epoch', create_time)", 'create_ts'),
        ('task.start_time', 'start_time'),
        ("date_part('epoch', task.start_time)", 'start_ts'),
        ('task.completion_time', 'completion_time'),
        ("date_part('epoch', completion_time)", 'completion_ts'),
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
        self.id = convert_value(id, cast=int)
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
        query = QueryProcessor(tables=['task'], columns=['state', 'host_id'],
                               clauses=['id=%(task_id)s'], values={'task_id': task_id},
                               opts={'rowlock': True})
        r = query.executeOne()
        if not r:
            raise koji.GenericError("No such task: %i" % task_id)
        return (r['state'] == koji.TASK_STATES['OPEN'] and r['host_id'] == host_id)

    def assertHost(self, host_id):
        if not self.verifyHost(host_id):
            raise koji.ActionNotAllowed("host %d does not own task %d" % (host_id, self.id))

    def getOwner(self):
        """Return the owner (user_id) for this task"""
        query = QueryProcessor(tables=['task'], columns=['owner'],
                               clauses=['id=%(id)i'], values=vars(self))
        return query.singleValue()

    def verifyOwner(self, user_id=None):
        """Verify that user owns task"""
        if user_id is None:
            user_id = context.session.user_id
        if user_id is None:
            return False
        task_id = self.id
        # getting a row lock on this task to ensure task state sanity
        query = QueryProcessor(tables=['task'], columns=['owner'],
                               clauses=['id=%(task_id)s'], values={'task_id': task_id},
                               opts={'rowlock': True})
        owner = query.singleValue(strict=False)
        if not owner:
            raise koji.GenericError("No such task: %i" % task_id)
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
        # note the QueryProcessor...opts={'rowlock': True}
        task_id = self.id
        if not force:
            query = QueryProcessor(columns=['state', 'host_id'], tables=['task'],
                                   clauses=['id=%(task_id)s'], values={'task_id': task_id},
                                   opts={'rowlock': True})
            r = query.executeOne()
            if not r:
                raise koji.GenericError("No such task: %i" % task_id)
            state = r['state']
            otherhost = r['host_id']
            if state == koji.TASK_STATES['FREE']:
                if otherhost is not None:
                    logger.error(f"Error: task {task_id} is both free "
                                 f"and handled by host {otherhost}")
                    return False
            elif state == koji.TASK_STATES['ASSIGNED']:
                if otherhost is None:
                    logger.error(f"Error: task {task_id} is assigned, but no host is really "
                                 "assigned")
                    return False
                elif otherhost != host_id:
                    # task is assigned to someone else, no error just return
                    return False
                elif newstate == 'ASSIGNED':
                    # double assign is a weird situation but we can return True as state doesn't
                    # really change
                    logger.error(f"Error: double assign of task {task_id} and host {host_id}")
                    return True
                # otherwise the task is assigned to host_id, so keep going
            elif state == koji.TASK_STATES['CANCELED']:
                # it is ok that task was canceled meanwhile
                return False
            elif state == koji.TASK_STATES['OPEN']:
                if otherhost is None:
                    logger.error(f"Error: task {task_id} is opened but not handled by any host")
                elif otherhost == host_id:
                    logger.error(f"Error: task {task_id} is already open and handled by "
                                 f"{host_id} (double open/assign)")
                return False
            else:
                # state is CLOSED or FAILED
                if otherhost is None:
                    logger.error(f"Error: task {task_id} is non-free but not handled by any host "
                                 f"(state {koji.TASK_STATES[state]})")
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
        # access checks should be performed by calling function
        query = QueryProcessor(tables=['task'], columns=['state'], clauses=['id = %(id)i'],
                               values=vars(self), opts={'rowlock': True})
        oldstate = query.singleValue(strict=False)
        if not oldstate:
            raise koji.GenericError("No such task: %i" % self.id)
        if koji.TASK_STATES[oldstate] in ['CLOSED', 'CANCELED', 'FAILED']:
            raise koji.GenericError("Cannot free task %i, state is %s" %
                                    (self.id, koji.TASK_STATES[oldstate]))
        newstate = koji.TASK_STATES['FREE']
        newhost = None
        update = UpdateProcessor('task', clauses=['id=%(task_id)s'], values={'task_id': self.id},
                                 data={'state': newstate, 'host_id': newhost})
        update.execute()
        self.runCallbacks('postTaskStateChange', info, 'state', koji.TASK_STATES['FREE'])
        self.runCallbacks('postTaskStateChange', info, 'host_id', None)
        return True

    def setWeight(self, weight):
        """Set weight for task"""
        weight = convert_value(weight, cast=float)
        info = self.getInfo(request=True)
        self.runCallbacks('preTaskStateChange', info, 'weight', weight)
        # access checks should be performed by calling function
        update = UpdateProcessor('task', clauses=['id=%(task_id)s'], values={'task_id': self.id},
                                 data={'weight': weight})
        update.execute()
        self.runCallbacks('postTaskStateChange', info, 'weight', weight)

    def setPriority(self, priority, recurse=False):
        """Set priority for task"""
        priority = convert_value(priority, cast=int)
        info = self.getInfo(request=True)
        self.runCallbacks('preTaskStateChange', info, 'priority', priority)
        # access checks should be performed by calling function
        update = UpdateProcessor('task', clauses=['id=%(task_id)s'], values={'task_id': self.id},
                                 data={'priority': priority})
        update.execute()
        self.runCallbacks('postTaskStateChange', info, 'priority', priority)

        if recurse:
            # Change priority of child tasks
            query = QueryProcessor(tables=['task'], columns=['id'],
                                   clauses=['parent = %(task_id)s'],
                                   values={'task_id': self.id},
                                   opts={'asList': True})
            for (child_id,) in query.execute():
                Task(child_id).setPriority(priority, recurse=True)

    def _close(self, result, state):
        """Mark task closed and set response

        Returns True if successful, False if not"""
        # access checks should be performed by calling function
        # this is an approximation, and will be different than what is in the database
        # the actual value should be retrieved from the 'new' value of the post callback
        now = time.time()
        info = self.getInfo(request=True)
        info['result'] = result
        self.runCallbacks('preTaskStateChange', info, 'state', state)
        self.runCallbacks('preTaskStateChange', info, 'completion_ts', now)
        # get the result from the info dict, so callbacks have a chance to modify it
        update = UpdateProcessor('task', clauses=['id = %(task_id)d'],
                                 values={'task_id': self.id},
                                 data={'result': info['result'], 'state': state},
                                 rawdata={'completion_time': 'NOW()'})
        update.execute()

        self.runCallbacks('postTaskStateChange', info, 'state', state)
        self.runCallbacks('postTaskStateChange', info, 'completion_ts', now)

    def close(self, result):
        # access checks should be performed by calling function
        self._close(result, koji.TASK_STATES['CLOSED'])

    def fail(self, result):
        # access checks should be performed by calling function
        self._close(result, koji.TASK_STATES['FAILED'])

    def getState(self):
        query = QueryProcessor(tables=['task'], columns=['state'], clauses=['id = %(id)i'],
                               values=vars(self))
        return query.singleValue()

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
        query = QueryProcessor(tables=['task'], columns=['state'], clauses=['id = %(task_id)s'],
                               values={'task_id': self.id}, opts={'rowlock': True})
        state = query.singleValue()
        st_canceled = koji.TASK_STATES['CANCELED']
        st_closed = koji.TASK_STATES['CLOSED']
        st_failed = koji.TASK_STATES['FAILED']
        if state == st_canceled:
            return True
        elif state in [st_closed, st_failed]:
            return False
        update = UpdateProcessor('task', clauses=['id = %(task_id)i'], values={'task_id': self.id},
                                 data={'state': st_canceled}, rawdata={'completion_time': 'NOW()'})
        update.execute()
        self.runCallbacks('postTaskStateChange', info, 'state', koji.TASK_STATES['CANCELED'])
        self.runCallbacks('postTaskStateChange', info, 'completion_ts', now)
        # cancel associated builds (only if state is 'BUILDING')
        # since we check build state, we avoid loops with cancel_build on our end
        b_building = koji.BUILD_STATES['BUILDING']
        query = QueryProcessor(tables=['build'], columns=['id'],
                               clauses=['task_id = %(task_id)i', 'state = %(b_building)i'],
                               values={'task_id': self.id, 'b_building': b_building},
                               opts={'rowlock': True, 'asList': True})
        for (build_id,) in query.execute():
            cancel_build(build_id, cancel_task=False)
        if recurse:
            # also cancel child tasks
            self.cancelChildren()
        return True

    def cancelChildren(self):
        """Cancel child tasks"""
        query = QueryProcessor(tables=['task'], columns=['id'], clauses=['parent = %(task_id)i'],
                               values={'task_id': self.id}, opts={'asList': True})
        for (id,) in query.execute():
            Task(id).cancel(recurse=True)

    def cancelFull(self, strict=True):
        """Cancel this task and every other task in its group

        If strict is true, then this must be a top-level task
        Otherwise we will follow up the chain to find the top-level task
        """
        task_id = self.id
        query = QueryProcessor(tables=['task'], columns=['parent'],
                               clauses=['id = %(task_id)i'],
                               values={'task_id': task_id}, opts={'rowlock': True})
        parent = query.singleValue(strict=False)
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
                query.values = {'task_id': task_id}
                parent = query.singleValue()
            return Task(task_id).cancelFull(strict=True)
        # We handle the recursion ourselves, since self.cancel will stop at
        # canceled or closed tasks.
        tasklist = [task_id]
        seen = {}
        # query for use in loop
        for task_id in tasklist:
            if task_id in seen:
                # shouldn't happen
                raise koji.GenericError("Task LOOP at task %i" % task_id)
            seen[task_id] = 1
            Task(task_id).cancel(recurse=False)
            query = QueryProcessor(tables=['task'], columns=['id'],
                                   clauses=['parent = %(task_id)i'],
                                   values={'task_id': task_id}, opts={'asList': True})
            for (child_id,) in query.execute():
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
        query = QueryProcessor(tables=['task'], columns=['state', 'result'],
                               clauses=['id = %(id)i'], values={'id': self.id})
        r = query.executeOne()
        if not r:
            raise koji.GenericError("No such task")
        state = r['state']
        xml_result = r['result']
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
            raise koji.GenericError('No such callback type: %s' % cbtype)
        old_val = old_info[attr]
        if attr == 'state':
            # state is passed in as an integer, but we want to use the string
            old_val = koji.TASK_STATES[old_val]
            new_val = koji.TASK_STATES[new_val]
        koji.plugin.run_callbacks(cbtype, attribute=attr, old=old_val, new=new_val,
                                  info=info)
