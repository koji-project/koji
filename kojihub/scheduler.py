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

    return query.execute()
