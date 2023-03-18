# scheduler code goes here

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

    def run(self):
        if not self.get_lock():
            # already running elsewhere
            return False

        runs = getTaskRuns()
        runs_by_task = {}
        for run in runs:
            runs_by_task.setdefault(run['task_id'], [])
            runs_by_task[run['task_id']].append(run)

        # get tasks
        active_tasks = self.get_tasks()
        # TODO need a better query, but this will do for now

        # get hosts and bin them
        hosts = get_ready_hosts()
        hosts_by_bin = {}
        for host in hosts:
            host['_bins'] = []
            for chan in host['channels']:
                for arch in host['arches'].split() + ['noarch']:
                    host_bin = "%s:%s" % (chan, arch)
                    hosts_by_bin.setdefault(host_bin, []).append(host)
                    host['_bins'].append(host_bin)

        for task in active_tasks:
            if task['state'] == koji.TASK_STATES['ASSIGNED']:
                # TODO -- sort out our interaction with old school assignments
                continue
            have_run = False
            task_runs = runs_by_task.get(task['id'], [])
            for run in task_runs:
                if run['state'] in OK_RUN_STATES:
                    have_run = True
                    break
            if have_run:
                continue
            elif task_runs:
                # TODO -- what to do about bad runs?
            else:
                # we need a run
                # XXX need host
                self.add_run(task, host)

        # indicate that scheduling ran
        return True

    def get_tasks(self):
        pass


    def get_task_data():
        joins = ('LEFT OUTER JOIN scheduler_task_runs ON task_id = task.id')

        fields = (
            ('task.id', 'task_id'),
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


        query = QueryProcessor(
            columns=fields, aliases=aliases, tables=['scheduler_task_runs'],
            joins=['LEFT OUTER JOIN host on host_id=host.id'],
            clauses=clauses, values=locals())

        data = query.execute()


    def add_run(self, task, host):
        insert = InsertProcessor('scheduler_runs')
        insert.set(task_id=task['id'], host_id=host['id'], state=1)
        insert.execute()

    def get_lock(self):
        # TODO
        pass
