import json
import logging
import time

import koji
from . import kojihub
from .db import QueryProcessor, InsertProcessor, UpdateProcessor, db_lock


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


def intlist(value):
    """Cast value to a list of ints"""
    if isinstance(value, (list, tuple)):
        return [int(n) for n in value]
    else:
        return [int(value)]


def get_tasks_for_host(hostID):
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
    )

    return query.execute()


def set_refusal(hostID, taskID, soft=True, by_host=False, msg=''):
    data = {
        'task_id': kojihub.convert_value(hostID, cast=int),
        'host_id': kojihub.convert_value(taskID, cast=int),
        'soft': kojihub.convert_value(soft, cast=bool),
        'by_host': kojihub.convert_value(by_host, cast=bool),
        'msg': kojihub.convert_value(msg, cast=str),
    }
    insert = InsertProcessor('scheduler_task_refusals', data=data)
    insert.execute()
    # note: db allows multiple entries here, but in general we shouldn't
    # make very many


def get_task_refusals(taskID=None, hostID=None):
    taskID = kojihub.convert_value(taskID, cast=int, none_allowed=True)
    hostID = kojihub.convert_value(hostID, cast=int, none_allowed=True)

    fields = (
        ('scheduler_task_refusals.id', 'id'),
        ('scheduler_task_refusals.task_id', 'task_id'),
        ('scheduler_task_refusals.host_id', 'host_id'),
        ('scheduler_task_refusals.by_host', 'by_host'),
        ('scheduler_task_refusals.soft', 'soft'),
        ('scheduler_task_refusals.msg', 'msg'),
        # ('host.name', 'host_name'),
        ("date_part('epoch', scheduler_task_refusals.time)", 'ts'),
    )
    fields, aliases = zip(*fields)

    clauses = []
    if taskID is not None:
        clauses.append('task_id = %(taskID)s')
    if hostID is not None:
        clauses.append('host_id = %(hostID)s')

    query = QueryProcessor(
        columns=fields, aliases=aliases, tables=['scheduler_task_refusals'],
        # joins=['host ON host_id=host.id', 'task ON task_id=task.id'],
        clauses=clauses, values=locals(),
        opts={'order': '-id'}
    )

    return query.execute()


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


def get_task_runs(taskID=None, hostID=None, active=None):
    taskID = kojihub.convert_value(taskID, cast=int, none_allowed=True)
    hostID = kojihub.convert_value(hostID, cast=int, none_allowed=True)
    active = kojihub.convert_value(active, cast=bool, none_allowed=True)

    fields = (
        ('scheduler_task_runs.id', 'id'),
        ('scheduler_task_runs.task_id', 'task_id'),
        ('scheduler_task_runs.host_id', 'host_id'),
        # ('host.name', 'host_name'),
        # ('task.method', 'method'),
        ('scheduler_task_runs.active', 'active'),
        ("date_part('epoch', scheduler_task_runs.create_time)", 'create_ts'),
    )
    fields, aliases = zip(*fields)

    clauses = []
    if taskID is not None:
        clauses.append('task_id = %(taskID)s')
    if hostID is not None:
        clauses.append('host_id = %(hostID)s')
    if active is not None:
        clauses.append('active = %(active)s')

    query = QueryProcessor(
        columns=fields, aliases=aliases, tables=['scheduler_task_runs'],
        # joins=['host ON host_id=host.id', 'task ON task_id=task.id'],
        clauses=clauses, values=locals())

    return query.execute()


class TaskScheduler(object):

    def __init__(self):
        self.hosts_by_bin = None
        self.hosts = None
        self.active_tasks = None
        self.free_tasks = None

        # TODO these things need proper config
        self.maxjobs = 15  # XXX
        self.capacity_overcommit = 5
        self.ready_timeout = 180
        self.assign_timeout = 300
        self.host_timeout = 900
        self.run_interval = 60

    def run(self):
        if not db_lock('scheduler', wait=False):
            # already running elsewhere
            return False

        if not self.check_ts():
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
        update = UpdateProcessor(
            'scheduler_sys_data',
            clauses=['name = %(name)s'],
            values={'name': 'last_run_ts'},
            data={'data': json.dumps(now)},
        )
        chk = update.execute()
        if not chk:
            # hasn't been defined yet
            insert = InsertProcessor(
                'scheduler_sys_data',
                data={'name': 'last_run_ts', 'data': json.dumps(now)},
            )
            insert.execute()

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
        for task in self.free_tasks:
            task['_hosts'] = []
            min_avail = min(0, task['weight'] - self.capacity_overcommit)
            for host in self.hosts_by_bin.get(task['_bin'], []):
                if (host['ready'] and host['_ntasks'] < self.maxjobs and
                        host['capacity'] - host['_load'] > min_avail):
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
                    self.add_run(task, host)
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
                log_both('Assigned task with no active run entry', task_id=task['task_id'],
                         host_id=host['id'], level=logging.ERROR)
                kojihub.Task(task['task_id']).free()
                continue

            if len(taskruns) > 1:
                logger.error('Multiple active run entries for assigned task %(task_id)s',
                             task)
                # TODO fix

            if task['state'] == koji.TASK_STATES['ASSIGNED']:
                # TODO check time since assigned
                # if not taken within a timeout
                #  - if host not checking in, then make sure host marked unavail and free
                #  - if host *is* checking in, then treat as refusal and free
                age = time.time() - min([r['create_ts'] for r in taskruns])
                if age > self.assign_timeout:
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

    def get_active_runs(self):
        runs = get_task_runs(active=True)
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

    def add_run(self, task, host):
        log_both('Assigning task', task_id=task['task_id'], host_id=host['id'])

        # mark any older runs inactive
        update = UpdateProcessor(
            'scheduler_task_runs',
            data={'active': False},
            clauses=['task_id=%(task_id)s', 'active = TRUE'],
            values={'task_id': task['task_id']},
        )
        update.execute()

        # add the new run
        insert = InsertProcessor('scheduler_task_runs')
        insert.set(task_id=task['task_id'], host_id=host['id'])
        insert.execute()

        # mark the task assigned
        update = UpdateProcessor(
            'task',
            data={'host_id': host['id'], 'state': koji.TASK_STATES['ASSIGNED']},
            clauses=['id=%(task_id)s', 'state=%(free)s'],
            values={'task_id': task['task_id'], 'free': koji.TASK_STATES['FREE']},
        )
        update.execute()


class SchedulerExports:
    getTaskRuns = staticmethod(get_task_runs)
    getHostData = staticmethod(get_host_data)
