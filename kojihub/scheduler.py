import json
import logging
import time

import koji
from koji.context import context
from . import kojihub
from .db import QueryProcessor, InsertProcessor, UpsertProcessor, UpdateProcessor, \
    DeleteProcessor, QueryView, db_lock


logger = logging.getLogger('koji.scheduler')


def log_db(msg, task_id=None, host_id=None):
    insert = InsertProcessor(
        'scheduler_log_messages',
        data={'msg': msg, 'task_id': task_id, 'host_id': host_id},
    )
    insert.execute()


def log_both(msg, task_id=None, host_id=None, level=logging.INFO):
    pre1 = f"[task_id={task_id}] " if task_id else ""
    pre2 = f"[host_id={host_id}] " if host_id else ""
    logger.log(level, '%s%s%s', pre1, pre2, msg)
    log_db(msg, task_id, host_id)


class LogMessagesQuery(QueryView):

    tables = ['scheduler_log_messages']
    joinmap = {
        # outer joins because these fields can be null
        'task': 'LEFT JOIN task ON scheduler_log_messages.task_id = task.id',
        'host': 'LEFT JOIN host ON scheduler_log_messages.host_id = host.id',
    }
    fieldmap = {
        'id': ['scheduler_log_messages.id', None],
        'task_id': ['scheduler_log_messages.task_id', None],
        'host_id': ['scheduler_log_messages.host_id', None],
        'msg_ts': ["date_part('epoch', scheduler_log_messages.msg_time)", None],
        'msg': ['scheduler_log_messages.msg', None],
        'method': ['task.method', 'task'],
        'state': ['task.state', 'task'],
        'owner': ['task.owner', 'task'],
        'arch': ['task.arch', 'task'],
        'channel_id': ['task.channel_id', 'task'],
        'host_name': ['host.name', 'host'],
        'host_ready': ['host.ready', 'host'],
    }
    default_fields = ('id', 'task_id', 'host_id', 'msg', 'msg_ts')


def get_log_messages(clauses=None, fields=None):
    return LogMessagesQuery(clauses, fields, opts={'order': 'id'}).execute()


def get_tasks_for_host(hostID, retry=True):
    """Get the tasks assigned to a given host"""
    hostID = kojihub.convert_value(hostID, cast=int, none_allowed=True)

    fields = (
        ('task.id', 'id'),
        ('task.state', 'state'),
        ('task.channel_id', 'channel_id'),
        ('task.host_id', 'host_id'),
        ('task.arch', 'arch'),
        ('task.method', 'method'),
        ('task.priority', 'priority'),
        ("date_part('epoch', create_time)", 'create_ts'),
    )
    fields, aliases = zip(*fields)

    query = QueryProcessor(
        columns=fields, aliases=aliases, tables=['task'],
        clauses=['host_id = %(hostID)s', 'state=%(assigned)s'],
        values={'hostID': hostID, 'assigned': koji.TASK_STATES['ASSIGNED']},
        opts={'order': 'priority,create_ts'},
    )

    tasks = query.execute()

    if not tasks and retry:
        # run scheduler and try again
        TaskScheduler().run()
        tasks = query.execute()

    return tasks


def set_refusal(hostID, taskID, soft=True, by_host=False, msg=''):
    data = {
        'host_id': kojihub.convert_value(hostID, cast=int),
        'task_id': kojihub.convert_value(taskID, cast=int),
        'soft': kojihub.convert_value(soft, cast=bool),
        'by_host': kojihub.convert_value(by_host, cast=bool),
        'msg': kojihub.convert_value(msg, cast=str),
    }
    upsert = UpsertProcessor('scheduler_task_refusals', data=data, keys=('task_id', 'host_id'))
    upsert.execute()
    log_both(f'Host refused task: {msg}', task_id=taskID, host_id=hostID)


class TaskRefusalsQuery(QueryView):

    tables = ['scheduler_task_refusals']
    joinmap = {
        'task': 'task ON scheduler_task_refusals.task_id = task.id',
        'host': 'host ON scheduler_task_refusals.host_id = host.id',
    }
    fieldmap = {
        'id': ['scheduler_task_refusals.id', None],
        'task_id': ['scheduler_task_refusals.task_id', None],
        'host_id': ['scheduler_task_refusals.host_id', None],
        'by_host': ['scheduler_task_refusals.by_host', None],
        'soft': ['scheduler_task_refusals.soft', None],
        'msg': ['scheduler_task_refusals.msg', None],
        'ts': ["date_part('epoch', scheduler_task_refusals.time)", None],
        'method': ['task.method', 'task'],
        'state': ['task.state', 'task'],
        'owner': ['task.owner', 'task'],
        'arch': ['task.arch', 'task'],
        'channel_id': ['task.channel_id', 'task'],
        'host_name': ['host.name', 'host'],
        'host_ready': ['host.ready', 'host'],
    }
    default_fields = ('id', 'task_id', 'host_id', 'by_host', 'soft', 'msg', 'ts')


def get_task_refusals(clauses=None, fields=None):
    return TaskRefusalsQuery(clauses, fields).execute()


def get_host_data(hostID=None):
    """Return actual builder data

    :param int hostID: Return data for given host (otherwise for all)
    :returns list[dict]: list of host_id/data dicts
    """
    clauses = []
    columns = ['host_id', 'data']
    if hostID is not None:
        clauses.append('host_id = %(hostID)i')
    query = QueryProcessor(
        tables=['scheduler_host_data'],
        clauses=clauses,
        columns=columns,
        values=locals(),
        opts={'order': 'host_id'}
    )

    return query.execute()


class TaskRunsQuery(QueryView):

    tables = ['scheduler_task_runs']
    joinmap = {
        'task': 'task ON scheduler_task_runs.task_id = task.id',
        'host': 'host ON scheduler_task_runs.host_id = host.id',
    }
    fieldmap = {
        'id': ['scheduler_task_runs.id', None],
        'task_id': ['scheduler_task_runs.task_id', None],
        'method': ['task.method', 'task'],
        'state': ['task.state', 'task'],
        'owner': ['task.owner', 'task'],
        'arch': ['task.arch', 'task'],
        'channel_id': ['task.channel_id', 'task'],
        'host_name': ['host.name', 'host'],
        'host_ready': ['host.ready', 'host'],
        'host_id': ['scheduler_task_runs.host_id', None],
        'active': ['scheduler_task_runs.active', None],
        'create_ts': ["date_part('epoch', scheduler_task_runs.create_time)", None],
        'start_ts': ["date_part('epoch', task.start_time)", 'task'],
        'completion_ts': ["date_part('epoch', task.completion_time)", 'task'],
    }
    default_fields = ('id', 'task_id', 'host_id', 'active', 'create_ts')


def get_task_runs(clauses=None, fields=None):
    return TaskRunsQuery(clauses, fields).execute()


class TaskScheduler(object):

    def __init__(self):
        self.hosts_by_bin = {}
        self.hosts = {}
        self.active_tasks = []
        self.free_tasks = []

        # TODO these things need proper config
        self.maxjobs = context.opts['MaxJobs']
        self.capacity_overcommit = context.opts['CapacityOvercommit']
        self.ready_timeout = context.opts['ReadyTimeout']
        self.assign_timeout = context.opts['AssignTimeout']
        self.soft_refusal_timeout = context.opts['SoftRefusalTimeout']
        self.host_timeout = context.opts['HostTimeout']
        self.run_interval = context.opts['RunInterval']

    def run(self, force=False):
        if not db_lock('scheduler', wait=force):
            # already running elsewhere
            return False

        if not force and not self.check_ts():
            # already ran too recently
            return False

        logger.info('Running task scheduler')
        self.get_tasks()
        self.get_hosts()
        self.check_hosts()
        self.do_schedule()
        self.check_active_tasks()

        return True

    def check_ts(self):
        """Check the last run timestamp

        Returns True if the scheduler should run, False otherwise
        """

        # get last ts
        query = QueryProcessor(
            tables=['scheduler_sys_data'],
            columns=['data'],
            clauses=['name = %(name)s'],
            values={'name': 'last_run_ts'},
        )
        last = query.singleValue(strict=False) or 0

        now = time.time()
        delta = now - last

        if delta < 0:
            logger.error('Last run in the future by %i seconds', -delta)
            ret = False
            # update the ts so that a system time rollback doesn't keep us from running
        elif delta < self.run_interval:
            logger.debug('Skipping run due to run_interval setting')
            # return now without updating ts
            return False
        else:
            ret = True

        # save current ts
        upsert = UpsertProcessor(
            'scheduler_sys_data',
            data={'name': 'last_run_ts',
                  'data': json.dumps(now)},
            keys=['name'],
        )
        upsert.execute()

        return ret

    def do_schedule(self):
        # debug
        logger.info(f'Hosts: {len(self.hosts)}')
        logger.info(f'Free tasks: {len(self.free_tasks)}')
        logger.info(f'Active tasks: {len(self.active_tasks)}')

        # calculate host load and task count
        for task in self.active_tasks:
            # for now, we mirror what kojid updateTasks has been doing
            host = self.hosts.get(task['host_id'])
            if not host:
                # not showing as ready
                # TODO log and deal with this condition
                continue
            host.setdefault('_load', 0.0)
            if not task['waiting']:
                host['_load'] += task['weight']
            host.setdefault('_ntasks', 0)
            host['_ntasks'] += 1

        for host in self.hosts.values():
            host.setdefault('_load', 0.0)
            host.setdefault('_ntasks', 0)
            host.setdefault('_demand', 0.0)
            # temporary test code
            logger.info(f'Host: {host}')
            ldiff = host['task_load'] - host['_load']
            if abs(ldiff) > 0.01:
                # this is expected in a number of cases, just observing
                logger.info(f'Host load differs by {ldiff:.2f}: {host}')

        # figure out which hosts *can* take each task
        # at the moment this is mostly just bin, but in the future it will be more complex
        refusals = self.get_refusals()
        for task in self.free_tasks:
            task['_hosts'] = []
            min_avail = min(0, task['weight'] - self.capacity_overcommit)
            h_refused = refusals.get(task['task_id'], {})
            for host in self.hosts_by_bin.get(task['_bin'], []):
                if (host['ready'] and host['_ntasks'] < self.maxjobs and
                        host['capacity'] - host['_load'] > min_avail and
                        host['id'] not in h_refused):
                    task['_hosts'].append(host)
            logger.info(f'Task {task["task_id"]}: {len(task["_hosts"])} options')
            for host in task['_hosts']:
                # demand gives us a rough measure of how much overall load is pending for the host
                host.setdefault('_demand', 0.0)
                host['_demand'] += task['weight'] / len(task['_hosts'])

        # normalize demand to 1
        max_demand = sum([h['_demand'] for h in self.hosts.values()])
        if max_demand > 0.0:
            for h in self.hosts.values():
                h['_demand'] = (h['_demand'] / max_demand)

        for h in self.hosts.values():
            self._rank_host(h)

        # tasks are already in priority order
        for task in self.free_tasks:
            min_avail = task['weight'] - self.capacity_overcommit
            task['_hosts'].sort(key=lambda h: h['_rank'])
            logger.debug('Task %i choices: %s', task['task_id'],
                         [(h['name'], "%(_rank).2f" % h) for h in task['_hosts']])
            for host in task['_hosts']:
                if (host['capacity'] - host['_load'] > min_avail and
                        host['_ntasks'] < self.maxjobs):
                    # add run entry
                    self.assign(task, host)
                    # update our totals and rank
                    host['_load'] += task['weight']
                    host['_ntasks'] += 1
                    self._rank_host(host)
                    break
            else:
                logger.debug('Could not assign task %s', task['task_id'])

    def _rank_host(self, host):
        host['_rank'] = host['_load'] + host['_ntasks'] + host['_demand']

    def check_active_tasks(self):
        """Check on active tasks"""
        runs = self.get_active_runs()
        logger.info('Found %i active runs', len(runs))
        logger.info('Checking on %i active tasks', len(self.active_tasks))
        for task in self.active_tasks:

            if not task['host_id']:
                log_both('Active task with no host', task_id=task['task_id'], level=logging.ERROR)
                kojihub.Task(task['task_id']).free()
                continue

            host = self.hosts.get(task['host_id'])
            if not host:
                # host disabled?
                # TODO
                continue

            taskruns = runs.get(task['task_id'], [])
            if not taskruns:
                # a task that is assigned without a run entry is treated as an override
                # we simply leave these alone
                # TODO track overrides more explicitly
                logger.debug('Override task assignment: task %i, host %s',
                             task['task_id'], host['name'])
                continue

            if len(taskruns) > 1:
                logger.error('Multiple active run entries for assigned task %(task_id)s',
                             task)
                # TODO fix

            if task['state'] == koji.TASK_STATES['ASSIGNED']:
                assign_ts = min([r['create_ts'] for r in taskruns])
                age = time.time() - assign_ts
                if age > self.assign_timeout:
                    # has the host checked in since we assigned?
                    if host['update_ts'] and host['update_ts'] > assign_ts:
                        # treat this as an implicit refusal
                        # possibly an older koji version on builder
                        set_refusal(host['id'], task['task_id'], msg='assignment timeout')
                    log_both('Task assignment timeout', task_id=task['task_id'],
                             host_id=host['id'])
                    kojihub.Task(task['task_id']).free()

            elif task['state'] == koji.TASK_STATES['OPEN']:
                if host['update_ts'] is None:
                    # shouldn't happen?
                    # fall back to task_run time
                    age = time.time() - min([r['create_ts'] for r in taskruns])
                else:
                    age = time.time() - host['update_ts']
                if age > self.host_timeout:
                    log_both('Freeing task from unresponsive host', task_id=task['task_id'],
                             host_id=host['id'])
                    kojihub.Task(task['task_id']).free()

        # end stale runs
        update = UpdateProcessor(
            'scheduler_task_runs',
            data={'active': False},
            clauses=['active = TRUE',
                     '(SELECT id FROM task WHERE task.id=task_id AND '
                     'state IN %(states)s) IS NULL'],
            values={'states': [koji.TASK_STATES[s] for s in ('OPEN', 'ASSIGNED')]},
        )
        update.execute()

    def check_hosts(self):
        # sanity check ready status
        hosts_to_mark = []
        for host in self.hosts.values():
            if not host['ready']:
                continue
            if (host['update_ts'] is None or time.time() - host['update_ts'] > self.ready_timeout):
                hosts_to_mark.append(host)
                log_both('Marking host not ready', host_id=host['id'])

        if hosts_to_mark:
            update = UpdateProcessor(
                'host',
                data={'ready': False},
                clauses=['id IN %(host_ids)s'],
                values={'host_ids': [h['id'] for h in hosts_to_mark]},
            )
            update.execute()
        # also update our data
        for host in hosts_to_mark:
            host['ready'] = False

    def get_active_runs(self):
        runs = get_task_runs([["active", True]])
        runs_by_task = {}
        for run in runs:
            runs_by_task.setdefault(run['task_id'], [])
            runs_by_task[run['task_id']].append(run)

        return runs_by_task

    def get_tasks(self):
        """Get the task data that we need for scheduling"""

        fields = (
            ('task.id', 'task_id'),
            ('task.state', 'state'),
            ('task.waiting', 'waiting'),
            ('task.weight', 'weight'),
            ('channel_id', 'channel_id'),
            ('task.host_id', 'host_id'),
            ('arch', 'arch'),
            ('method', 'method'),
            ('priority', 'priority'),
            ("date_part('epoch', task.create_time)", 'create_ts'),
            # ('scheduler_task_runs.id', 'run_id'),
        )
        fields, aliases = zip(*fields)

        values = {'states': [koji.TASK_STATES[n] for n in ('ASSIGNED', 'OPEN')]}

        query = QueryProcessor(
            columns=fields, aliases=aliases, tables=['task'],
            clauses=('task.state IN %(states)s',
                     'task.host_id IS NOT NULL',  # should always be set, but...
                     ),
            values=values,
        )
        active_tasks = query.execute()

        values = {'state': koji.TASK_STATES['FREE']}
        query = QueryProcessor(
            columns=fields, aliases=aliases, tables=['task'],
            clauses=('task.state = %(state)s',),
            values=values,
            opts={'order': 'priority,create_ts', 'limit': 1000},  # TODO config
            # scheduler order
            # lower priority numbers take precedence, like posix process priority
            # at a given priority, earlier creation times take precedence
        )
        free_tasks = query.execute()

        for task in free_tasks:
            tbin = '%(channel_id)s:%(arch)s' % task
            task['_bin'] = tbin

        for task in active_tasks:
            tbin = '%(channel_id)s:%(arch)s' % task
            task['_bin'] = tbin

        self.free_tasks = free_tasks
        self.active_tasks = active_tasks

    def get_refusals(self):
        """Get task refusals and clean stale entries"""
        refusals = {}
        cutoff_ts = time.time() - self.soft_refusal_timeout
        to_drop = []
        for row in get_task_refusals(fields=('id', 'task_id', 'host_id', 'soft', 'ts', 'state')):
            if ((row['soft'] and row['ts'] < cutoff_ts) or
                    koji.TASK_STATES[row['state']] not in ('FREE', 'OPEN', 'ASSIGNED')):
                to_drop.append(row['id'])
            else:
                # index by task and host
                refusals.setdefault(row['task_id'], {})[row['host_id']] = row

        if to_drop:
            # drop stale entries
            delete = DeleteProcessor(
                'scheduler_task_refusals',
                clauses=['id IN %(to_drop)s'],
                values=locals(),
            )
            delete.execute()

        return refusals

    def get_hosts(self):
        # get hosts and bin them
        hosts_by_bin = {}
        hosts_by_id = {}
        for host in self._get_hosts():
            host['_bins'] = []
            hosts_by_id[host['id']] = host
            for chan in host['channels']:
                for arch in host['arches'].split() + ['noarch']:
                    host_bin = "%s:%s" % (chan, arch)
                    hosts_by_bin.setdefault(host_bin, []).append(host)
                    host['_bins'].append(host_bin)

        self.hosts_by_bin = hosts_by_bin
        self.hosts = hosts_by_id

    def _get_hosts(self):
        """Query enabled hosts"""

        fields = (
            ('host.id', 'id'),
            ('host.name', 'name'),
            ("date_part('epoch', host.update_time)", 'update_ts'),
            ('host.task_load', 'task_load'),
            ('host.ready', 'ready'),
            ('host_config.arches', 'arches'),
            ('host_config.capacity', 'capacity'),
        )
        fields, aliases = zip(*fields)

        query = QueryProcessor(
            tables=['host'],
            columns=fields,
            aliases=aliases,
            clauses=[
                'host_config.enabled IS TRUE',
                'host_config.active IS TRUE',
            ],
            joins=[
                'host_config ON host.id = host_config.host_id'
            ]
        )

        hosts = query.execute()

        # also get channel info
        query = QueryProcessor(
            tables=['host_channels'],
            columns=['host_id', 'channel_id'],
            clauses=['active IS TRUE', 'channels.enabled IS TRUE'],
            joins=['channels ON host_channels.channel_id = channels.id'],
        )
        chan_idx = {}
        for row in query.execute():
            chan_idx.setdefault(row['host_id'], []).append(row['channel_id'])
        for host in hosts:
            host['channels'] = chan_idx.get(host['id'], [])

        return hosts

    def assign(self, task, host, force=False, override=False):
        # mark the task assigned
        success = kojihub.Task(task['task_id']).assign(host['id'], force=force)
        if not success:
            log_both('Assignment failed', task_id=task['task_id'], host_id=host['id'])
            return False

        if override:
            log_both('Assigning task (override)', task_id=task['task_id'], host_id=host['id'])
        else:
            log_both('Assigning task', task_id=task['task_id'], host_id=host['id'])

        # mark any older runs inactive
        update = UpdateProcessor(
            'scheduler_task_runs',
            data={'active': False},
            clauses=['task_id=%(task_id)s', 'active = TRUE'],
            values={'task_id': task['task_id']},
        )
        update.execute()

        if not override:
            # add the new run
            insert = InsertProcessor('scheduler_task_runs')
            insert.set(task_id=task['task_id'], host_id=host['id'])
            insert.execute()
        # In the override case, we omit the run entry

        return True


# exported as assignTask in kojihub
def do_assign(task_id, host, force=False, override=False):
    """Assign a task to a host

    Specify force=True to assign a non-free task
    Specify override=True to prevent the scheduler from reassigning later
    """
    task_id = kojihub.convert_value(task_id, cast=int)
    host = kojihub.get_host(host, strict=True)
    force = kojihub.convert_value(force, cast=bool)
    override = kojihub.convert_value(override, cast=bool)
    context.session.assertPerm('admin')
    task = {'task_id': task_id}  # the assign call just needs the task_id field
    db_lock('scheduler', wait=True)
    return TaskScheduler().assign(task, host, force=force, override=override)


class SchedulerExports:
    getTaskRuns = staticmethod(get_task_runs)
    getTaskRefusals = staticmethod(get_task_refusals)
    getHostData = staticmethod(get_host_data)
    getLogMessages = staticmethod(get_log_messages)

    def doRun(self, force=False):
        """Run the scheduler

        This is a debug tool and should not normally be needed.
        Scheduler runs are regularly triggered by builder checkins
        """

        force = kojihub.convert_value(force, cast=bool)
        context.session.assertPerm('admin')
        return TaskScheduler().run(force=force)
