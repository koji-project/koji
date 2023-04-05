import logging
import psycopg2

import koji
from .db import QueryProcessor, db_lock
from .util import convert_value
from koji.context import context


logger = logging.getLogger('koji.scheduler')
# TODO set up db logging


class DBLogger:
    pass


class SchedulerExports:
    pass


def intlist(value):
    """Cast value to a list of ints"""
    if isinstance(value, (list, tuple)):
        return [int(n) for n in value]
    else:
        return [int(value)]


def getTaskRuns(taskID=None, hostID=None, state=None):
    taskID = convert_value(taskID, cast=int, none_allowed=True)
    hostID = convert_value(hostID, cast=int, none_allowed=True)
    state = convert_value(state, cast=intlist, none_allowed=True)

    fields = (
        ('scheduler_task_runs.id', 'id'),
        ('task_id', 'task_id'),
        ('host_id', 'host_id'),
        ('host.name', 'host_name'),
        ('state', 'state'),
        ("date_part('epoch', create_time)", 'create_ts'),
        ("date_part('epoch', start_time)", 'start_ts'),
        ("date_part('epoch', end_time)", 'end_ts'),
    )
    fields, aliases = zip(*fields)

    clauses = []
    if taskID is not None:
        clauses.append('task_id = %(taskID)s')
    if hostID is not None:
        clauses.append('host_id = %(hostID)s')
    if state is not None:
        clauses.append('host_id IN %(state)s')

    query = QueryProcessor(
        columns=fields, aliases=aliases, tables=['scheduler_task_runs'],
        joins=['LEFT OUTER JOIN host on host_id=host.id'],
        clauses=clauses, values=locals())

    data = query.execute()


def scheduler_map_task(taskinfo):
    # map which hosts can take this task
    # eventually this will involve more complex rules
    q = QueryProcessor()
    # select hosts matching arch and channel
    hosts = q.execute()
    u = InsertProcessor()


class TaskScheduler(object):

    def __init__(self):
        self.hosts_by_bin = None
        self.hosts = None
        self.tasks_by_bin = None
        self.active_tasks = None
        self.maxjobs = 15  # XXX

    def run(self):
        if not db_lock('scheduler', wait=False):
            # already running elsewhere
            return False

        self.do_schedule()
        # TODO clean up bad data (e.g. active tasks with no host)
        # TODO check for runs that aren't getting picked up

        return True

    def get_runs(self):
        runs = getTaskRuns()
        runs_by_task = {}
        for run in runs:
            runs_by_task.setdefault(run['task_id'], [])
            runs_by_task[run['task_id']].append(run)

    def do_schedule(self):
        self.get_tasks()
        self.get_hosts()

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
            # temporary test code
            logger.info(f'Host: {host}')
            ldiff = host['task_load'] - host['_load']
            if abs(ldiff) > 0.01:
                # this is expected in a number of cases, just observing
                logger.info(f'Host load differs by {ldiff:.2f}: {host}')

        # order bins by available host capacity
        order = []
        for _bin in self.hosts_by_bin:
            hosts = self.hosts_by_bin.get(_bin, [])
            avail = sum([min(0, h['capacity'] - h['_load']) for h in hosts])
            order.append((avail, _bin))
        order.sort()

        # note bin demand for each host
        for n, (avail, _bin) in enumerate(order):
            rank = float(n) / len(order)
            for host in self.hosts_by_bin.get(_bin, []):
                host.setdefault('_rank', rank)
                # so host rank is set by the most contentious bin it covers
                # TODO - we could be smarter here, but it's a start

        # sort binned hosts by rank
        for _bin in self.hosts_by_bin:
            hosts = self.hosts_by_bin[_bin]
            hosts.sort(key=lambda h: h['_rank'], reverse=True)
            # hosts with least contention first

        # tasks are already in priority order
        for task in self.free_tasks:
            hosts = self.hosts_by_bin.get(task['_bin'], [])
            # these are the hosts that _can_ take this task
            # TODO - update host ranks as we go
            # TODO - pick a host and assign


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
        for host in self.get_ready_hosts():
            host['_bins'] = []
            hosts_by_id[host['id']] = host
            for chan in host['channels']:
                for arch in host['arches'].split() + ['noarch']:
                    host_bin = "%s:%s" % (chan, arch)
                    hosts_by_bin.setdefault(host_bin, []).append(host)
                    host['_bins'].append(host_bin)

        self.hosts_by_bin = hosts_by_bin
        self.hosts = hosts_by_id

    def get_ready_hosts(self):
        """Query hosts that are ready to build"""

        fields = (
            ('host.id', 'id'),
            ('host.name', 'name'),
            ('host.task_load', 'task_load'),
            ('host_config.arches', 'arches'),
            ('host_config.capacity', 'capacity'),
            ("date_part('epoch', sessions.update_time)", 'update_ts'),
        )
        fields, aliases = zip(*fields)

        query = QueryProcessor(
            tables=['host'],
            columns=fields,
            aliases=aliases,
            clauses=[
                'host.ready IS TRUE',
                'host_config.enabled IS TRUE',
                'host_config.active IS TRUE',
                'sessions.expired IS FALSE',
                'sessions.master IS NULL',
                "sessions.update_time > NOW() - '5 minutes'::interval"
            ],
            joins=[
                'sessions USING (user_id)',
                'host_config ON host.id = host_config.host_id'
            ]
        )

        hosts = query.execute()
        for host in hosts:
            query = QueryProcessor(
                tables=['host_channels'],
                columns=['channel_id'],
                clauses=['host_id=%(id)s', 'active IS TRUE', 'enabled IS TRUE'],
                joins=['channels ON host_channels.channel_id = channels.id'],
                values=host
            )
            rows = query.execute()
            host['channels'] = [row['channel_id'] for row in rows]

        return hosts

    def add_run(self, task, host):
        insert = InsertProcessor('scheduler_runs')
        insert.set(task_id=task['id'], host_id=host['id'], state=koji.TASK_STATES['ASSIGNED'])
        insert.execute()
