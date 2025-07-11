import datetime
from unittest import mock
import unittest

import koji
import kojihub
import kojihub.db
from kojihub import scheduler


QP = scheduler.QueryProcessor
IP = scheduler.InsertProcessor
UP = scheduler.UpdateProcessor
TASK = kojihub.Task


class MyError(Exception):
    pass


class BaseTest(unittest.TestCase):

    def setUp(self):
        self.context = mock.patch('kojihub.scheduler.context').start()
        self.context.opts = {
            # duplicating hub defaults
            'MaxJobs': 15,
            'CapacityOvercommit':5,
            'ReadyTimeout': 180,
            'AssignTimeout': 300,
            'SoftRefusalTimeout': 900,
            'HostTimeout': 900,
            'RunInterval': 60,
        }

        self.db_lock = mock.patch('kojihub.scheduler.db_lock').start()
        self.db_lock.return_value = True

        self.QueryProcessor = mock.patch('kojihub.scheduler.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.InsertProcessor = mock.patch('kojihub.scheduler.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.scheduler.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self._dml = mock.patch('kojihub.db._dml').start()
        self.exports = kojihub.RootExports()
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.query_executeOne = mock.MagicMock()

        self.get_task_refusals = mock.patch('kojihub.scheduler.get_task_refusals').start()
        self.get_task_runs = mock.patch('kojihub.scheduler.get_task_runs').start()
        self.check_repo_queue = mock.patch('kojihub.repos.check_repo_queue').start()

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = self.query_executeOne
        self.queries.append(query)
        return query

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update


class TestLogging(BaseTest):

    def test_log_both(self):
        msg = 'Does logging work?'
        scheduler.log_both(msg, host_id=1, task_id=2)
        self.assertEqual(len(self.inserts), 1)
        expected = {'msg': msg, 'host_id': 1, 'task_id': 2}
        self.assertEqual(self.inserts[0].data, expected)


class TestScheduler(BaseTest):

    def setUp(self):
        super(TestScheduler, self).setUp()

    def test_ran_recently(self):
        s = scheduler.TaskScheduler()
        # scheduler should not run if check_ts says not to
        s.check_ts = mock.MagicMock(return_value=False)
        s.get_tasks = mock.MagicMock(side_effect=MyError('should not reach unless forced'))
        s.run()
        self.assertEqual(len(self.queries), 0)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)
        # ... unless we use force
        with self.assertRaises(MyError):
            s.run(force=True)

    def test_no_lock(self):
        self.db_lock.return_value = False
        s = scheduler.TaskScheduler()
        s.get_tasks = mock.MagicMock(side_effect=MyError('should not reach'))
        s.run()
        self.assertEqual(len(self.queries), 0)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    def test_run(self):
        s = scheduler.TaskScheduler()
        s.check_ts = mock.MagicMock(return_value=True)
        s.run()
        # TODO


class TestDoSchedule(BaseTest):

    def setUp(self):
        super(TestDoSchedule, self).setUp()
        self.sched = scheduler.TaskScheduler()
        self.sched.get_refusals = mock.MagicMock()
        self.sched._get_hosts = mock.MagicMock()
        self.assigns = []
        self.sched.assign = mock.MagicMock(side_effect=self.my_assign)

    def my_assign(self, task, host):
        self.assigns.append((task,host))

    def test_no_hosts_no_tasks(self):
        self.sched._get_hosts.return_value = []
        self.sched.get_hosts()
        self.sched.do_schedule()

        self.sched.assign.assert_not_called()
        self.assertEqual(len(self.queries), 0)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    def mktask(self, **kw):
        data = kw.copy()
        data.setdefault('host_id', None)
        data.setdefault('waiting', False)
        data.setdefault('weight', 1.0)
        data.setdefault('channel_id', 1)
        data.setdefault('arch', 'noarch')
        data.setdefault('_bin', '%(channel_id)s:%(arch)s' % data)
        data.setdefault('task_id', mock.MagicMock())  # ??
        return data

    def mkhost(self, **kw):
        data = kw.copy()
        data.setdefault('task_load', 0.0)
        data.setdefault('ready', True)
        data.setdefault('data', None)
        data.setdefault('capacity', 10.0)
        data.setdefault('channels', [1])
        data.setdefault('arches', 'x86_64')
        data.setdefault('id', mock.MagicMock())  # ??
        data.setdefault('name', f'Host {data["id"]}')  # ??
        return data

    def test_no_hosts_free_tasks(self):
        self.sched._get_hosts.return_value = []
        self.sched.get_hosts()
        self.sched.free_tasks = [self.mktask(task_id=n) for n in range(5)]

        self.sched.do_schedule()

        self.sched.assign.assert_not_called()
        self.assertEqual(len(self.queries), 0)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    def test_no_tasks_avail_hosts(self):
        self.sched._get_hosts.return_value = [self.mkhost(id=n) for n in range(5)]
        self.sched.get_hosts()
        self.sched.free_tasks = []

        self.sched.do_schedule()

        self.sched.assign.assert_not_called()
        self.assertEqual(len(self.queries), 0)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    def test_no_tasks_avail_hosts(self):
        self.sched._get_hosts.return_value = [self.mkhost(id=n) for n in range(5)]
        self.sched.get_hosts()
        self.sched.free_tasks = []

        self.sched.do_schedule()

        self.sched.assign.assert_not_called()
        self.assertEqual(len(self.queries), 0)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    def test_free_tasks_avail_hosts(self):
        self.sched._get_hosts.return_value = [self.mkhost(id=n) for n in range(5)]
        self.sched.get_hosts()
        self.sched.free_tasks = [self.mktask(task_id=n) for n in range(5)]

        self.sched.do_schedule()

        # in this simple case, tasks should be evenly assigned
        self.assertEqual(len(self.assigns), 5)
        t_assigned = []
        h_used = []
        for task, host in self.assigns:
            t_assigned.append(task['task_id'])
            h_used.append(host['id'])
        t_assigned.sort()
        h_used.sort()
        self.assertEqual(t_assigned, list(range(5)))
        self.assertEqual(h_used, list(range(5)))

    def test_stop_at_capacity(self):
        # just one host
        host = self.mkhost(id=1, capacity=5.0)
        self.sched._get_hosts.return_value = [host]
        self.sched.get_hosts()
        # and more tasks than will fit
        self.sched.free_tasks = [self.mktask(task_id=n, weight=1.0) for n in range(10)]

        self.sched.do_schedule()

        # 5 tasks with weight=1.0 should fill up capacity
        # (overcommit only applies for a single task going over)
        self.assertEqual(len(self.assigns), 5)
        t_assigned = [t['task_id'] for t, h in self.assigns]
        t_assigned.sort()
        self.assertEqual(t_assigned, list(range(5)))

    def test_active_tasks(self):
        self.context.opts['CapacityOvercommit'] = 1.0
        hosts = [self.mkhost(id=n, capacity=2.0) for n in range(5)]
        active = [self.mktask(task_id=n, host_id=n, weight=4.0) for n in range(3)]
        # so, first three hosts have a task of weight=4, more than capacity+overcommit
        free = [self.mktask(task_id=n, weight=2.0) for n in range(3,5)]
        # two free tasks with weight=2
        self.sched._get_hosts.return_value = hosts
        self.sched.get_hosts()
        self.sched.free_tasks = free
        self.sched.active_tasks = active

        self.sched.do_schedule()

        # we expect that the two free tasks will be assigned evenly to the hosts with free capacity
        self.assertEqual(len(self.assigns), 2)
        t_assigned = []
        h_used = []
        for task, host in self.assigns:
            t_assigned.append(task['task_id'])
            h_used.append(host['id'])
        t_assigned.sort()
        h_used.sort()
        self.assertEqual(t_assigned, list(range(3,5)))
        self.assertEqual(h_used, list(range(3,5)))

class TestCheckActiveRuns(BaseTest):

    def setUp(self):
        super(TestCheckActiveRuns, self).setUp()
        self.sched = scheduler.TaskScheduler()

        self.get_active_runs = mock.MagicMock()
        self.sched.get_active_runs = self.get_active_runs

        self.frees = []
        self.assigns = []
        def my_free(task):
            self.frees.append(task.id)
        def my_assign(task, host_id, force=False):
            self.assigns.append((task.id, host_id, force))
        mock.patch('kojihub.Task.free', new=my_free).start()
        mock.patch('kojihub.Task.assign', new=my_assign).start()
        self.log_db = mock.MagicMock()
        mock.patch('kojihub.scheduler.log_db', new=self.log_db).start()
        self.set_refusal = mock.patch('kojihub.scheduler.set_refusal').start()

    def test_check_no_active(self):
        self.assertEqual(self.sched.active_tasks, [])  # set by init
        self.sched.check_active_tasks()
        # with no active tasks, we shouldn't have done much
        self.get_active_runs.assert_called_once()
        self.assertEqual(self.frees, [])
        self.assertEqual(self.assigns, [])
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'scheduler_task_runs')

    def test_check_no_host(self):
        # 'Active task with no host' case
        self.sched.active_tasks = [{'task_id': 99, 'host_id': None}]
        self.sched.check_active_tasks()
        self.log_db.assert_called_once_with('Active task with no host', 99, None)
        self.get_active_runs.assert_called_once()
        self.assertEqual(self.frees, [99])
        self.assertEqual(self.assigns, [])
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'scheduler_task_runs')

    def test_check_override(self):
        # 'Override task assignment' case
        self.sched.active_tasks = [{'task_id': 99, 'host_id': 23, 'state': koji.TASK_STATES['ASSIGNED']}]
        self.sched.hosts = {23: {'id': 23, 'name': 'test host 23'}}
        self.sched.get_active_runs.return_value = {}
        with mock.patch('kojihub.scheduler.logger') as _logger:
            self.sched.check_active_tasks()
            _logger.debug.assert_called_once_with('Override task assignment: task %i, host %s',
                                                  99, 'test host 23')
        self.get_active_runs.assert_called_once()
        # this case is not logged to the db
        self.log_db.assert_not_called()
        # we should not free such tasks
        self.assertEqual(self.frees, [])
        self.assertEqual(self.assigns, [])
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'scheduler_task_runs')

    def test_check_assign_timeout(self):
        # 'Task assignment timeout' case
        create_ts = 1000
        update_ts = 999  # host ts BEFORE assignment
        now = 1000000
        self.sched.active_tasks = [{'task_id': 99, 'host_id': 23, 'state': koji.TASK_STATES['ASSIGNED']}]
        self.sched.hosts = {23: {'id': 23, 'name': 'test host 23', 'update_ts': update_ts}}
        self.sched.get_active_runs.return_value = {99: [{'create_ts': create_ts}]}

        with mock.patch('time.time', return_value=now):
            self.sched.check_active_tasks()

        self.get_active_runs.assert_called_once()
        self.set_refusal.assert_not_called()
        self.log_db.assert_called_once_with('Task assignment timeout', 99, 23)
        # we should free such tasks
        self.assertEqual(self.frees, [99])
        self.assertEqual(self.assigns, [])
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'scheduler_task_runs')

    def test_check_implicit_refusal(self):
        # 'Task assignment timeout' case
        create_ts = 1000
        update_ts = 1001  # host ts AFTER assignment
        now = 1000000
        self.sched.active_tasks = [{'task_id': 99, 'host_id': 23, 'state': koji.TASK_STATES['ASSIGNED']}]
        self.sched.hosts = {23: {'id': 23, 'name': 'test host 23', 'update_ts': update_ts}}
        self.sched.get_active_runs.return_value = {99: [{'create_ts': create_ts}]}

        with mock.patch('time.time', return_value=now):
            self.sched.check_active_tasks()

        self.get_active_runs.assert_called_once()
        self.set_refusal.assert_called_once_with(23, 99, msg='assignment timeout')
        self.log_db.assert_called_once_with('Task assignment timeout', 99, 23)
        # we should free such tasks
        self.assertEqual(self.frees, [99])
        self.assertEqual(self.assigns, [])
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'scheduler_task_runs')

    def test_check_unresponsive(self):
        # 'Freeing task from unresponsive host' case
        now = 1000000
        create_ts = 0
        update_ts = 0
        self.sched.active_tasks = [{'task_id': 99, 'host_id': 23, 'state': koji.TASK_STATES['OPEN']}]
        self.sched.hosts = {23: {'id': 23, 'name': 'test host 23', 'update_ts': update_ts}}
        self.sched.get_active_runs.return_value = {99: [{'create_ts': create_ts}]}
        with mock.patch('time.time', return_value=now):
            self.sched.check_active_tasks()
        self.get_active_runs.assert_called_once()
        # we should free such tasks
        self.log_db.assert_called_once_with('Freeing task from unresponsive host', 99, 23)
        self.assertEqual(self.frees, [99])
        self.assertEqual(self.assigns, [])
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'scheduler_task_runs')
