import datetime
import mock
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
        create_ts = 0
        now = 1000000
        self.sched.active_tasks = [{'task_id': 99, 'host_id': 23, 'state': koji.TASK_STATES['ASSIGNED']}]
        self.sched.hosts = {23: {'id': 23, 'name': 'test host 23'}}
        self.sched.get_active_runs.return_value = {99: [{'create_ts': create_ts}]}
        with mock.patch('time.time', return_value=now):
            self.sched.check_active_tasks()
        self.get_active_runs.assert_called_once()
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
