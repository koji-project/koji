import logging
import psycopg2

import koji
from .db import QueryProcessor, InsertProcessor, UpdateProcessor, db_lock
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


def get_tasks_for_host(hostID):
    """Get the tasks assigned to a given host"""
    hostID = convert_value(hostID, cast=int, none_allowed=True)

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


def getTaskRuns(taskID=None, hostID=None, state=None):
    taskID = convert_value(taskID, cast=int, none_allowed=True)
    hostID = convert_value(hostID, cast=int, none_allowed=True)
    state = convert_value(state, cast=intlist, none_allowed=True)

    fields = (
        ('scheduler_task_runs.id', 'id'),
        ('scheduler_task_runs.task_id', 'task_id'),
        ('scheduler_task_runs.host_id', 'host_id'),
        ('host.name', 'host_name'),
        ('task.method', 'method'),
        ('scheduler_task_runs.state', 'state'),
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
        joins=['host ON host_id=host.id', 'task ON task_id=task.id'],
        clauses=clauses, values=locals())

    data = query.execute()
    return data


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
        self.free_tasks = None
        self.maxjobs = 15  # XXX
        self.capacity_overcommit = 5  # TODO config

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
            min_avail = task['weight'] + self.capacity_overcommit
            for host in self.hosts_by_bin.get(task['_bin'], []):
                if (host['capacity'] > host['_load'] and
                        host['_ntasks'] < self.maxjobs and
                        host['capacity'] - host['_load'] > min_avail):
                    task['_hosts'].append(host)
            logger.info(f'Task {task["task_id"]}: {len(task["_hosts"])} options')
            for host in task['_hosts']:
                # demand gives us a rough measure of how much overall load is pending for the host
                host.setdefault('_demand', 0.0)
                host['_demand'] += task['weight'] / len(task['_hosts'])

        # tasks are already in priority order
        for task in self.free_tasks:
            # pick the host with least demand
            task['_hosts'].sort(key=lambda h: h['_demand'])
            min_avail = task['weight'] + self.capacity_overcommit
            for host in task['_hosts']:
                if (host['capacity'] > host['_load'] and
                        host['_ntasks'] < self.maxjobs and
                        host['capacity'] - host['_load'] > min_avail):
                    # add run entry
                    self.add_run(task, host)
                    # update our totals
                    host['_load'] += task['weight']
                    host['_ntasks'] += 1

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
        insert = InsertProcessor('scheduler_task_runs')
        insert.set(task_id=task['task_id'], host_id=host['id'], state=koji.TASK_STATES['ASSIGNED'])
        insert.execute()
        update = UpdateProcessor(
                'task',
                data={'host_id': host['id'], 'state': koji.TASK_STATES['ASSIGNED']},
                clauses=['id=%(task_id)s', 'state=%(free)s'],
                values={'task_id': task['task_id'], 'free': koji.TASK_STATES['FREE']},
        )
        update.execute()
