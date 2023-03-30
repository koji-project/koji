# scheduler code goes here

import koji
from .db import QueryProcessor
from .util import convert_value


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

    def run(self):
        if not self.get_lock():
            # already running elsewhere
            return False

        self.do_schedule()
        return True

    def do_schedule(self):
        # get tasks to schedule
        tasks = self.get_free_tasks()
        tasks_by_bin = {}
        for task in tasks:
            tbin = '%(channel_id)s:%(arch)s' % task
            task['_bin'] = tbin
            tasks_by_bin.setdefault(tbin, []).append(task)

        # get hosts and bin them
        hosts = self.get_ready_hosts()
        hosts_by_bin = {}
        for host in hosts:
            host['_bins'] = []
            for chan in host['channels']:
                for arch in host['arches'].split() + ['noarch']:
                    host_bin = "%s:%s" % (chan, arch)
                    hosts_by_bin.setdefault(host_bin, []).append(host)
                    host['_bins'].append(host_bin)

        # order bins by available host capacity
        order = []
        for _bin in hosts_by_bin:
            hosts = hosts_by_bin.get(_bin, [])
            avail = sum([min(0, h['capacity'] - h['task_load']) for h in hosts])
            order.append((avail, _bin))
        order.sort()

        # note bin demand for each host
        for n, (avail, _bin) in enumerate(order):
            rank = float(n) / len(order)
            for host in hosts_by_bin.get(_bin, []):
                host.setdefault('_rank', rank)
                # so host rank is set by the most contentious bin it covers
                # TODO - we could be smarter here, but it's a start

        # sort binned hosts by rank
        for _bin in hosts_by_bin:
            hosts = hosts_by_bin[_bin]
            hosts.sort(key=lambda h: h._rank, reverse=True)
            # hosts with least contention first

        # tasks are already in priority order
        for task in tasks:
            hosts = hosts_by_bin.get(task['_bin'], [])
            # these are the hosts that _can_ take this task
            # TODO - update host ranks as we go
            # TODO - pick a host and assign


    def get_free_tasks(self):
        """Get the tasks that need scheduling"""

        fields = (
            ('task.id', 'task_id'),
            ('task.state', 'state'),
            ('channel_id', 'channel_id'),
            ('task.host_id', 'host_id'),
            ('arch', 'arch'),
            ('method', 'method'),
            ('priority', 'priority'),
            ("date_part('epoch', task.create_time)", 'create_ts'),
            # ('scheduler_task_runs.id', 'run_id'),
        )
        fields, aliases = zip(*fields)

        values = {'states': [koji.TASK_STATES[n] for n in ('FREE',)]}

        query = QueryProcessor(
            columns=fields, aliases=aliases, tables=['task'],
            # joins=('LEFT OUTER JOIN scheduler_task_runs ON task_id = task.id'),
            # clauses=('task.state IN %(states)s', 'run_id IS NULL'),
            clauses=('task.state IN %(states)s',),
            values=values,
            opts={'order': 'priority,create_ts'},
            # scheduler order
            # lower priority numbers take precedence, like posix process priority
            # at a given priority, earlier creation times take precedence
        )

        return query.execute()

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
                'enabled IS TRUE',
                'ready IS TRUE',
                'expired IS FALSE',
                'master IS NULL',
                'active IS TRUE',
                "update_time > NOW() - '5 minutes'::interval"
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
        insert.set(task_id=task['id'], host_id=host['id'], state=1)
        insert.execute()

    def get_lock(self):
        # TODO
        return True  # XXX
