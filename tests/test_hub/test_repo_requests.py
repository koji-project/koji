import json
import shutil
import tempfile
import unittest

from unittest import mock

import koji
import kojihub
import kojihub.db
from kojihub import repos


QP = repos.QueryProcessor
IP = repos.InsertProcessor
UP = repos.UpdateProcessor
TASK = kojihub.Task


class MyError(Exception):
    pass


class BaseTest(unittest.TestCase):

    def setUp(self):
        self.context = mock.MagicMock()
        self.context.session.assertLogin = mock.MagicMock()
        self.getLastEvent = mock.MagicMock()
        self.getEvent = mock.MagicMock()
        self.context.handlers = {
            'getLastEvent': self.getLastEvent,
            'getEvent': self.getEvent,
        }
        mock.patch('kojihub.repos.context', new=self.context).start()
        mock.patch('kojihub.db.context', new=self.context).start()
        mock.patch('kojihub.kojihub.context', new=self.context).start()
        self.context.opts = {
            # duplicating hub defaults
            'MaxRepoTasks': 10,
            'MaxRepoTasksMaven': 2,
            'RepoRetries': 3,
            'RequestCleanTime': 60 * 24,
            'RepoLag': 3600,
            'RepoAutoLag': 7200,
            'RepoLagWindow': 600,
            'RepoQueueUser': 'kojira',
            'DebuginfoTags': '',
            'SourceTags': '',
            'SeparateSourceTags': '',
            'EnableMaven': False,
        }

        self.QueryProcessor = mock.patch('kojihub.repos.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.InsertProcessor = mock.patch('kojihub.repos.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.repos.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self._dml = mock.patch('kojihub.db._dml').start()
        self.exports = kojihub.RootExports()
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.get_id = mock.patch('kojihub.kojihub.get_id').start()
        self.make_task = mock.patch('kojihub.kojihub.make_task').start()
        self.tag_last_change_event = mock.patch('kojihub.kojihub.tag_last_change_event').start()
        self.tag_first_change_event = mock.patch('kojihub.kojihub.tag_first_change_event').start()
        self.query_execute = mock.MagicMock()
        self.query_executeOne = mock.MagicMock()
        self.query_singleValue = mock.MagicMock()

        self.RepoQueueQuery = mock.patch('kojihub.repos.RepoQueueQuery').start()
        self.RepoQuery = mock.patch('kojihub.repos.RepoQuery').start()
        self.nextval = mock.patch('kojihub.repos.nextval').start()

    def tearDown(self):
        mock.patch.stopall()

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = self.query_execute
        query.executeOne = self.query_executeOne
        query.singleValue = self.query_singleValue
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


class TestRepoQueue(BaseTest):

    def setUp(self):
        super(TestRepoQueue, self).setUp()
        self.clean_repo_queue = mock.patch('kojihub.repos.clean_repo_queue').start()
        self.repo_queue_task = mock.patch('kojihub.repos.repo_queue_task').start()
        self.get_repo_from_task = mock.patch('kojihub.repos.get_repo_from_task').start()
        self.valid_repo = mock.patch('kojihub.repos.valid_repo').start()
        self.db_lock = mock.patch('kojihub.repos.db_lock').start()
        self.db_lock.return_value = True

    def test_nolock(self):
        self.db_lock.return_value = False
        repos.check_repo_queue()
        self.db_lock.assert_called_once()
        self.RepoQueueQuery.assert_not_called()

    def test_check_queue_full(self):
        self.context.opts['MaxRepoTasks'] = 10
        basereq = {'task_state': koji.TASK_STATES['FREE'], 'opts': {}, 'tries': 1}
        # 10 reqs with free tasks
        reqs = [dict({'id': n, 'task_id': 100 + n}, **basereq) for n in range(10)]
        # plus one with no task
        reqs.append({'id': 99, 'task_id': None, 'task_state': None, 'opts': {}, 'tries': 1})
        self.RepoQueueQuery.return_value.execute.return_value = reqs

        repos.check_repo_queue()

        self.repo_queue_task.assert_not_called()
        self.UpdateProcessor.assert_not_called()
        self.clean_repo_queue.assert_not_called()

    def test_check_maven_full(self):
        self.context.opts['MaxRepoTasksMaven'] = 2
        basereq = {'task_state': koji.TASK_STATES['FREE'], 'opts': {'maven': True}, 'tries': 1}
        # 2 maven reqs with free tasks
        reqs = [dict({'id': n, 'task_id': 100 + n}, **basereq) for n in range(2)]
        # plus two more, one maven, one not
        req_a = {'id': 98, 'task_id': None, 'task_state': None, 'opts': {'maven': True},
                 'tries': 1}
        req_b = {'id': 99, 'task_id': None, 'task_state': None, 'opts': {}, 'tries': 1}
        reqs.extend([req_a, req_b])
        self.RepoQueueQuery.return_value.execute.return_value = reqs

        repos.check_repo_queue()

        # only the non-maven should get a task
        self.repo_queue_task.assert_called_once_with(req_b)
        self.UpdateProcessor.assert_called_once()
        self.clean_repo_queue.assert_called_once()

    def test_check_queue_filled(self):
        # fill up the queue
        self.context.opts['MaxRepoTasks'] = 10
        basereq = {'task_state': koji.TASK_STATES['FREE'], 'opts': {}, 'tries': 1}
        # 9 reqs with free tasks
        reqs = [dict({'id': n, 'task_id': 100 + n}, **basereq) for n in range(9)]
        # plus two more
        req_a = {'id': 98, 'task_id': None, 'task_state': None, 'opts': {}, 'tries': 1}
        req_b = {'id': 99, 'task_id': None, 'task_state': None, 'opts': {}, 'tries': 1}
        reqs.extend([req_a, req_b])
        self.RepoQueueQuery.return_value.execute.return_value = reqs

        repos.check_repo_queue()

        # req_a should be fulfilled, but not req_b
        self.repo_queue_task.assert_called_once_with(req_a)
        self.UpdateProcessor.assert_called_once()
        self.clean_repo_queue.assert_called_once()

    def test_check_queue_filled_maven(self):
        # fill up the queue
        self.context.opts['MaxRepoTasks'] = 10
        self.context.opts['MaxRepoTasksMaven'] = 2
        base1 = {'task_state': koji.TASK_STATES['FREE'], 'opts': {}, 'tries': 1}
        base2 = {'task_state': koji.TASK_STATES['FREE'], 'opts': {'maven': True}, 'tries': 1}
        # 7 reqs with free tasks
        reqs = [dict({'id': n, 'task_id': 100 + n}, **base1) for n in range(7)]
        # 1 maven req with free tasks
        reqs.append(dict({'id': 7, 'task_id': 107}, **base2))
        # plus 4 more, two maven, two not
        req_a = {'id': 96, 'task_id': None, 'task_state': None, 'opts': {'maven': True},
                 'tries': 1}
        req_b = {'id': 97, 'task_id': None, 'task_state': None, 'opts': {'maven': True},
                 'tries': 1}
        req_c = {'id': 98, 'task_id': None, 'task_state': None, 'opts': {}, 'tries': 1}
        req_d = {'id': 99, 'task_id': None, 'task_state': None, 'opts': {}, 'tries': 1}
        reqs.extend([req_a, req_b, req_c, req_d])
        self.RepoQueueQuery.return_value.execute.return_value = reqs

        repos.check_repo_queue()

        # req_a and req_c should be fulfilled, but not b or d
        expected = [mock.call(req_a), mock.call(req_c)]
        self.assertEqual(self.repo_queue_task.call_args_list, expected)
        self.clean_repo_queue.assert_called_once()

    def test_check_queue_retry(self):
        self.context.opts['MaxRepoTasks'] = 10
        self.context.opts['MaxRepoTasksMaven'] = 2
        self.context.opts['RepoRetries'] = 3
        base = {'id': 100, 'task_id': 200, 'task_state': koji.TASK_STATES['FREE'], 'opts': {},
                'tries': 1}
        # these should get retries
        reqs1 = [
            dict(base, task_state=koji.TASK_STATES['CANCELED']),
            dict(base, task_state=koji.TASK_STATES['CANCELED'], tries=3),
            dict(base, task_state=koji.TASK_STATES['FAILED']),
            dict(base, task_state=koji.TASK_STATES['FAILED'], tries=3),
        ]
        # these should not
        reqs2 = [
            dict(base, task_state=koji.TASK_STATES['OPEN']),
            dict(base, task_state=koji.TASK_STATES['FREE']),
            dict(base, task_state=koji.TASK_STATES['CANCELED'], tries=4),
            dict(base, task_state=koji.TASK_STATES['FAILED'], tries=4),
        ]

        self.RepoQueueQuery.return_value.execute.return_value = reqs1 + reqs2

        repos.check_repo_queue()

        expected = [mock.call(r) for r in reqs1]
        self.assertEqual(self.repo_queue_task.call_args_list, expected)
        self.assertEqual(len(self.UpdateProcessor.mock_calls), 8)
        self.clean_repo_queue.assert_called_once()

    def test_check_queue_badrepo1(self):
        req = {'id': 100, 'task_id': 200, 'task_state': koji.TASK_STATES['CLOSED'], 'opts': {},
               'tries': 1}
        self.RepoQueueQuery.return_value.execute.return_value = [req]
        self.get_repo_from_task.return_value = None
        # should retry

        repos.check_repo_queue()

        self.repo_queue_task.assert_called_once_with(req)
        self.UpdateProcessor.assert_called_once()
        self.clean_repo_queue.assert_called_once()

    def test_check_queue_badrepo2(self):
        req = {'id': 100, 'task_id': 200, 'task_state': koji.TASK_STATES['CLOSED'], 'opts': {},
               'tries': 1}
        self.RepoQueueQuery.return_value.execute.return_value = [req]
        self.get_repo_from_task.return_value = 'REPO'
        self.valid_repo.return_value = False
        # should retry

        repos.check_repo_queue()

        self.repo_queue_task.assert_called_once_with(req)
        self.UpdateProcessor.assert_called_once()
        self.clean_repo_queue.assert_called_once()

    def test_check_queue_goodrepo(self):
        req = {'id': 100, 'task_id': 200, 'task_state': koji.TASK_STATES['CLOSED'], 'opts': {},
               'tries': 1}
        self.RepoQueueQuery.return_value.execute.return_value = [req]
        repo = {'id': 123, 'sentinel': 'hello 123dfs'}
        self.get_repo_from_task.return_value = repo
        self.valid_repo.return_value = True
        # should update, not retry

        repos.check_repo_queue()

        self.repo_queue_task.assert_not_called()
        self.UpdateProcessor.assert_called_once()
        self.clean_repo_queue.assert_called_once()


class TestRepoFromTask(BaseTest):

    def setUp(self):
        super(TestRepoFromTask, self).setUp()
        self.Task = mock.patch('kojihub.kojihub.Task').start()

    def test_valid(self):
        result = [1234, "ignored event id"]
        self.Task.return_value.getResult.return_value = result
        self.RepoQuery.return_value.execute.return_value = ["REPO"]

        repo = repos.get_repo_from_task("TASK_ID")

        self.assertEqual(repo, "REPO")
        self.Task.assert_called_once_with("TASK_ID")
        self.RepoQuery.assert_called_once_with([['id', '=', 1234]])

    def test_missing(self):
        result = [1234, "ignored event id"]
        self.Task.return_value.getResult.return_value = result
        self.RepoQuery.return_value.execute.return_value = []

        repo = repos.get_repo_from_task("TASK_ID")

        self.assertEqual(repo, None)
        self.Task.assert_called_once_with("TASK_ID")
        self.RepoQuery.assert_called_once_with([['id', '=', 1234]])

    def test_invalid(self):
        result = ["invalid: not an int", "ignored event id"]
        self.Task.return_value.getResult.return_value = result
        self.RepoQuery.return_value.execute.return_value = []

        repo = repos.get_repo_from_task("TASK_ID")

        self.assertEqual(repo, None)
        self.Task.assert_called_once_with("TASK_ID")
        self.RepoQuery.assert_not_called()


class TestRepoRequests(BaseTest):

    def test_clean_queue(self):
        repos.clean_repo_queue()

    def test_valid_repo(self):
        # match
        req = {'id': 101,
               'at_event': None,
               'min_event': 101010,
               'opts': {},
               'tag_id': 42,
               'tag_name': 'TAG'}
        repo = {'id': 999,
                'tag_id': 42,
                'begin_event': 497440,
                'create_event': 101020,
                'custom_opts': {},
                'dist': False,
                'opts': {'debuginfo': False, 'separate_src': False, 'src': False},
                'state': 1}
        check = repos.valid_repo(req, repo)
        self.assertTrue(check)

        # wrong tag
        bad = repo.copy()
        bad['tag_id'] = 99
        check = repos.valid_repo(req, bad)
        self.assertFalse(check)

        # wrong state
        bad = repo.copy()
        bad['state'] = 2
        check = repos.valid_repo(req, bad)
        self.assertFalse(check)

        # wrong event
        bad = repo.copy()
        bad['create_event'] = 101000
        check = repos.valid_repo(req, bad)
        self.assertFalse(check)

        # wrong at_event
        req2 = req.copy()
        req2.update(min_event=None, at_event=10000)
        bad = repo.copy()
        bad['create_event'] = 101000
        check = repos.valid_repo(req2, bad)
        self.assertFalse(check)

        # different opt value
        bad = repo.copy()
        bad['opts'] = {'debuginfo': True, 'separate_src': False, 'src': False}
        bad['custom_opts'] = {'debuginfo': True}
        check = repos.valid_repo(req, bad)
        self.assertFalse(check)

        # missing opt value
        req2 = req.copy()
        req2.update(opts={'debuginfo': True})
        bad = repo.copy()
        bad['opts'] = {'separate_src': False, 'src': False}
        bad['custom_opts'] = {'debuginfo': True}
        check = repos.valid_repo(req2, bad)
        self.assertFalse(check)

        # wrong custom opts
        req2 = req.copy()
        req2.update(opts={'src': True})
        bad = repo.copy()
        bad['opts'] = {'debuginfo': True, 'separate_src': False, 'src': False}
        bad['custom_opts'] = {'debuginfo': True}
        check = repos.valid_repo(req2, bad)
        self.assertFalse(check)

        # invalid opts
        req2 = req.copy()
        req2.update(opts={'src': True})
        bad = repo.copy()
        bad['opts'] = {}
        # opts field should never be blank
        bad['custom_opts'] = {}
        check = repos.valid_repo(req2, bad)
        self.assertFalse(check)


class TestDoneHook(BaseTest):

    def setUp(self):
        super(TestDoneHook, self).setUp()
        self.Savepoint = mock.patch('kojihub.repos.Savepoint').start()

    def test_simple(self):
        repos.repo_done_hook(100)

    def test_no_repo(self):
        self.RepoQuery.return_value.executeOne.return_value = None

        # should return without error
        repos.repo_done_hook(100)

        # should not query further or update
        self.RepoQueueQuery.assert_not_called()
        self.UpdateProcessor.assert_not_called()

        # no exception
        self.Savepoint.return_value.rollback.assert_not_called()

    def test_dist_repo(self):
        self.RepoQuery.return_value.executeOne.return_value = {'dist': True}

        # hook should not process dist repos
        repos.repo_done_hook(100)

        # should not query further or update
        self.RepoQueueQuery.assert_not_called()
        self.UpdateProcessor.assert_not_called()
        # no exception
        self.Savepoint.return_value.rollback.assert_not_called()

    def test_invalid_repo(self):
        # hook should not process invalid repos
        self.RepoQuery.return_value.executeOne.return_value = {'dist': False, 'opts': None,
                                                               'custom_opts': {}}

        repos.repo_done_hook(100)

        # should not query further or update
        self.RepoQueueQuery.assert_not_called()
        self.UpdateProcessor.assert_not_called()
        # no exception
        self.Savepoint.return_value.rollback.assert_not_called()

    def test_no_match(self):
        repo = {'dist': False, 'opts': {}, 'custom_opts': {}, 'tag_id': 'TAGID',
                'create_event': 101010}
        self.RepoQuery.return_value.executeOne.return_value = repo
        self.RepoQueueQuery.return_value.execute.return_value = []

        repos.repo_done_hook(100)

        self.assertEqual(len(self.RepoQueueQuery.call_args_list), 2)
        # should not update
        self.UpdateProcessor.assert_not_called()
        # no exception
        self.Savepoint.return_value.rollback.assert_not_called()

    def test_match(self):
        repo = {'id': 55, 'dist': False, 'opts': {}, 'custom_opts': {}, 'tag_id': 'TAGID',
                'create_event': 101010}
        self.RepoQuery.return_value.executeOne.return_value = repo
        req = {'id': 'REQ_ID'}
        self.RepoQueueQuery.return_value.execute.side_effect = [[req], []]

        repos.repo_done_hook(100)

        self.assertEqual(len(self.RepoQueueQuery.call_args_list), 2)
        # should not update
        self.UpdateProcessor.assert_called_once()
        update = self.updates[0]
        self.assertEqual(update.table, 'repo_queue')
        self.assertEqual(update.values, {'ids': ['REQ_ID']})
        self.assertEqual(update.data, {'repo_id': 55, 'active': False})
        # no exception
        self.Savepoint.return_value.rollback.assert_not_called()

    def test_exception(self):
        self.RepoQuery.side_effect = MyError()

        # should return without error
        repos.repo_done_hook(100)

        # should not query further or update
        self.RepoQueueQuery.assert_not_called()
        self.UpdateProcessor.assert_not_called()

        # rollback should be called
        self.Savepoint.return_value.rollback.assert_called_once()


class TestSymlink(BaseTest):

    def setUp(self):
        super(TestSymlink, self).setUp()
        self.tempdir = tempfile.mkdtemp()
        self.pathinfo = koji.PathInfo(self.tempdir)
        mock.patch('koji.pathinfo', new=self.pathinfo).start()
        self.symlink = mock.patch('os.symlink').start()
        self.lexists = mock.patch('os.path.lexists').start()
        self.unlink = mock.patch('os.unlink').start()
        self.lexists.return_value = False

    def tearDown(self):
        super(TestSymlink, self).tearDown()
        shutil.rmtree(self.tempdir)

    def test_skip_custom(self):
        repo = {'dist': False, 'custom_opts': {'src': True}}

        result = repos.symlink_if_latest(repo)

        self.assertFalse(result)
        self.RepoQuery.assert_not_called()
        self.symlink.assert_not_called()

    def test_skip_old(self):
        repo = {'dist': False, 'custom_opts': {}, 'tag_id': 'TAGID', 'create_event': 101010}
        self.RepoQuery.return_value.execute.return_value = ['REPO']

        result = repos.symlink_if_latest(repo)

        self.assertFalse(result)
        self.symlink.assert_not_called()

        # and same for a dist repo
        repo['dist'] = True
        result = repos.symlink_if_latest(repo)
        self.assertFalse(result)
        self.symlink.assert_not_called()

    def test_symlink(self):
        repo = {'id': 99, 'dist': False, 'custom_opts': {}, 'tag_id': 'TAGID',
                'create_event': 101010, 'tag_name': 'MYTAG'}
        self.RepoQuery.return_value.execute.return_value = []
        self.lexists.return_value = False

        result = repos.symlink_if_latest(repo)

        self.assertTrue(result)
        expect = self.tempdir + '/repos/MYTAG/latest'
        self.symlink.assert_called_with('99', expect)
        self.unlink.assert_not_called()

    def test_symlink_dist(self):
        repo = {'id': 99, 'dist': True, 'custom_opts': {}, 'tag_id': 'TAGID',
                'create_event': 101010, 'tag_name': 'MYTAG'}
        self.RepoQuery.return_value.execute.return_value = []

        result = repos.symlink_if_latest(repo)

        self.assertTrue(result)
        expect = self.tempdir + '/repos-dist/MYTAG/latest'
        self.symlink.assert_called_with('99', expect)

    def test_symlink_replace(self):
        repo = {'id': 99, 'dist': False, 'custom_opts': {}, 'tag_id': 'TAGID',
                'create_event': 101010, 'tag_name': 'MYTAG'}
        self.RepoQuery.return_value.execute.return_value = []
        self.lexists.return_value = True

        result = repos.symlink_if_latest(repo)

        self.assertTrue(result)
        expect = self.tempdir + '/repos/MYTAG/latest'
        self.unlink.assert_called_once_with(expect)
        self.symlink.assert_called_with('99', expect)

    def test_symlink_fail(self):
        repo = {'id': 99, 'dist': False, 'custom_opts': {}, 'tag_id': 'TAGID',
                'create_event': 101010, 'tag_name': 'MYTAG'}
        self.RepoQuery.return_value.execute.return_value = []
        self.symlink.side_effect = OSError('failed')

        result = repos.symlink_if_latest(repo)

        self.assertFalse(result)
        self.symlink.assert_called_once()


class TestQueueTask(BaseTest):

    def setUp(self):
        super(TestQueueTask, self).setUp()
        self.ensuredir = mock.patch('koji.ensuredir').start()

    def test_queue_task(self):
        req = {'id': 100, 'tag_id': 42, 'tag_name': 'tag 100',
               'min_event': None, 'at_event': None, 'opts': None}
        req['opts'] = {}

        repos.repo_queue_task(req)

        self.make_task.assert_called_once()

    def test_queue_task_event(self):
        req = {'id': 100, 'tag_id': 42, 'tag_name': 'tag 100',
               'min_event': None, 'at_event': 101010, 'opts': None}
        req['opts'] = {}

        repos.repo_queue_task(req)

        self.make_task.assert_called_once()
        method, args = self.make_task.call_args.args
        taskopts = self.make_task.call_args.kwargs
        self.assertEqual(method, 'newRepo')
        self.assertEqual(taskopts['channel'], 'createrepo')
        params = koji.tasks.parse_task_params('newRepo', args)
        self.assertEqual(params['event'], 101010)


class TestUpdateEndEvents(BaseTest):

    def setUp(self):
        super(TestUpdateEndEvents, self).setUp()
        self.BulkUpdateProcessor = mock.patch('kojihub.repos.BulkUpdateProcessor').start()

    def test_no_update(self):
        repo = {'id': 1, 'tag_id': 99, 'create_event': 1000}
        self.RepoQuery.return_value.execute.return_value = [repo]
        self.tag_first_change_event.return_value = None
        self.tag_last_change_event.return_value = 1000

        repos.update_end_events()

        self.BulkUpdateProcessor.assert_not_called()

    def test_update(self):
        repo = {'id': 1, 'tag_id': 99, 'create_event': 1000}
        self.RepoQuery.return_value.execute.return_value = [repo]
        self.tag_first_change_event.return_value = 1001

        repos.update_end_events()

        self.tag_last_change_event.assert_not_called()
        expect = [{'id': 1, 'end_event': 1001}]
        self.BulkUpdateProcessor.assert_called_once()
        updates = self.BulkUpdateProcessor.call_args.kwargs['data']
        self.assertEqual(updates, expect)

    def test_event_cache(self):
        # two current and one obsolete. all same tag
        repolist = [
            {'id': 1, 'tag_id': 99, 'create_event': 1000},
            # first is current, populates tag_last cache
            {'id': 2, 'tag_id': 99, 'create_event': 1000},
            {'id': 3, 'tag_id': 99, 'create_event': 1000},
            # 2 and 3 avoid checking tag due to cache
            {'id': 4, 'tag_id': 99, 'create_event': 999},
            # 4 is obsolete
        ]
        self.tag_last_change_event.return_value = 1000
        self.RepoQuery.return_value.execute.return_value = repolist
        self.tag_first_change_event.side_effect = [None, 1000]
        # the latter should only be called twice due to cache

        repos.update_end_events()

        self.tag_last_change_event.assert_called_once_with(99)
        expect_calls = [
            mock.call(99, after=1000),
            mock.call(99, after=999),
        ]
        self.assertEqual(self.tag_first_change_event.mock_calls, expect_calls)
        expect_updates = [{'id': 4, 'end_event': 1000}]
        self.BulkUpdateProcessor.assert_called_once()
        updates = self.BulkUpdateProcessor.call_args.kwargs['data']
        self.assertEqual(updates, expect_updates)


class TestExternalRepo(BaseTest):

    def setUp(self):
        super(TestExternalRepo, self).setUp()
        self.get_external_repo_id = mock.patch('kojihub.kojihub.get_external_repo_id').start()

    def test_get_external(self):
        self.get_external_repo_id.return_value = 42
        self.query_singleValue.return_value = 'DATA'

        data = repos.get_external_repo_data('my_ext_repo')

        self.assertEqual(data, 'DATA')
        self.QueryProcessor.assert_called_once()
        query = self.queries[0]
        self.assertEqual(query.tables, ['external_repo_data'])
        self.assertEqual(query.values, {'id': 42})

    def test_set_external(self):
        self.get_external_repo_id.return_value = 42
        self.query_singleValue.return_value = 'DATA'

        data = {'max_ts': 1717171717}
        repos.set_external_repo_data('my_ext_repo', data)

        self.UpdateProcessor.assert_called_once()
        self.InsertProcessor.assert_called_once()
        insert = self.inserts[0]
        self.assertEqual(insert.data['external_repo_id'], 42)
        self.assertEqual(json.loads(insert.data['data']), data)


class TestAutoRequests(BaseTest):

    def setUp(self):
        super(TestAutoRequests, self).setUp()
        self.request_repo = mock.patch('kojihub.repos.request_repo').start()
        self.tag_last_change_event = mock.patch('kojihub.kojihub.tag_last_change_event').start()
        self.time = mock.patch('time.time').start()

    def test_auto_requests(self):
        autokeys = [
            {'tag_id': 99, 'key': 'repo.auto', 'value': 'true'},
        ]
        self.query_execute.return_value = autokeys
        self.getLastEvent.return_value = {'id': 1050}
        self.tag_last_change_event.return_value = 1000
        self.request_repo.return_value = {'repo': None, 'request': 'REQ', 'duplicate': False}

        repos.do_auto_requests()

        self.request_repo.assert_called_once_with(99, min_event=1000, priority=5)

    def test_no_tags(self):
        autokeys = []
        self.query_execute.return_value = autokeys
        self.request_repo.assert_not_called()
        self.tag_last_change_event.assert_not_called()

    def test_bad_row(self):
        autokeys = [
            {'tag_id': 99, 'key': 'repo.auto', 'value': 'true'},
            {'tag_id': 98, 'key': 'repo.auto', 'value': 'not+valid+json'},
            {'tag_id': 98, 'key': 'repo.lag', 'value': '"valid json, but not valid int"'},
        ]
        # the bad rows should be ignored without blocking other auto requests
        self.query_execute.return_value = autokeys
        self.getLastEvent.return_value = {'id': 1050}
        self.tag_last_change_event.return_value = 1000
        self.request_repo.return_value = {'repo': None, 'request': 'REQ', 'duplicate': False}

        repos.do_auto_requests()

        self.request_repo.assert_called_once_with(99, min_event=1000, priority=5)

    def test_blocked_row(self):
        autokeys = [
            {'tag_id': 99, 'key': 'repo.auto', 'value': 'true'},
            {'tag_id': 98, 'key': 'repo.auto', 'value': None},
        ]
        # the blocked row should be ignored without blocking other auto requests
        self.query_execute.return_value = autokeys
        self.getLastEvent.return_value = {'id': 1050}
        self.tag_last_change_event.return_value = 1000
        self.request_repo.return_value = {'repo': None, 'request': 'REQ', 'duplicate': False}

        repos.do_auto_requests()

        self.request_repo.assert_called_once_with(99, min_event=1000, priority=5)

    def test_auto_lag(self):
        # use a trivial window to simplify the lag calculation
        self.context.opts['RepoLagWindow'] = 1
        autokeys = [
            {'tag_id': 99, 'key': 'repo.auto', 'value': 'true'},
            {'tag_id': 99, 'key': 'repo.lag', 'value': '0'},
        ]
        now = 1717171717
        self.time.return_value = now
        self.query_execute.return_value = autokeys
        self.getLastEvent.return_value = {'id': 1050}
        self.tag_last_change_event.return_value = 1000
        self.request_repo.return_value = {'repo': None, 'request': 'REQ', 'duplicate': True}

        repos.do_auto_requests()

        self.request_repo.assert_called_once_with(99, min_event=1000, priority=5)
        # with zero lag, getLastEvent should be called with current time
        self.getLastEvent.assert_called_once_with(before=now, strict=False)

    def test_auto_lag_window(self):
        self.context.opts['RepoLagWindow'] = 600
        autokeys = [
            {'tag_id': 99, 'key': 'repo.auto', 'value': 'true'},
            {'tag_id': 99, 'key': 'repo.lag', 'value': '0'},
        ]
        now = 1717171717
        self.time.return_value = now
        self.query_execute.return_value = autokeys
        self.getLastEvent.return_value = {'id': 1050}
        self.tag_last_change_event.return_value = 1000
        self.request_repo.return_value = {'repo': None, 'request': 'REQ', 'duplicate': False}

        repos.do_auto_requests()

        self.request_repo.assert_called_once_with(99, min_event=1000, priority=5)
        # with zero lag, getLastEvent should be called with current time
        self.getLastEvent.assert_called_once()
        before = self.getLastEvent.call_args.kwargs['before']
        # should be earlier than current time, but within lag window
        if before > now or before < now - 600:
            raise Exception('Invalid lag calculation')

    def test_no_last_tag_event(self):
        # corner case that should not happen
        autokeys = [
            {'tag_id': 99, 'key': 'repo.auto', 'value': 'true'},
        ]
        self.query_execute.return_value = autokeys
        self.tag_last_change_event.return_value = None

        repos.do_auto_requests()

        self.request_repo.assert_not_called()
        self.tag_last_change_event.assert_called_once()

    def test_no_last_event(self):
        # corner case that can happen with very new instances
        autokeys = [
            {'tag_id': 99, 'key': 'repo.auto', 'value': 'true'},
        ]
        self.getLastEvent.return_value = None
        self.query_execute.return_value = autokeys
        self.tag_last_change_event.return_value = 1000
        self.tag_first_change_event.return_value = 990
        self.request_repo.return_value = {'repo': None, 'request': 'REQ', 'duplicate': False}

        repos.do_auto_requests()

        self.request_repo.assert_called_once_with(99, min_event=990, priority=5)
        self.tag_last_change_event.assert_called_once()
        self.tag_first_change_event.assert_called_once()

        repos.do_auto_requests()


class TestGetRepo(BaseTest):

    def test_get_repo_simple(self):
        self.RepoQuery.return_value.executeOne.return_value = 'REPO'

        repo = repos.get_repo('TAGID')

        self.assertEqual(repo, 'REPO')
        self.RepoQuery.assert_called_once()

    def test_get_repo_at_event(self):
        repos.get_repo('TAGID', at_event=101010)

        self.RepoQuery.assert_called_once()
        clauses, fields, qopts = self.RepoQuery.call_args.args
        self.assertIn(['create_event', '=', 101010], clauses)

    def test_get_repo_min_event(self):
        repos.get_repo('TAGID', min_event=101010)

        self.RepoQuery.assert_called_once()
        clauses, fields, qopts = self.RepoQuery.call_args.args
        self.assertIn(['create_event', '>=', 101010], clauses)


class TestGetRepoOpts(BaseTest):

    def test_basic(self):
        taginfo = {'extra': {}}

        opts, custom = repos.get_repo_opts(taginfo)

        expect = {'src': False, 'debuginfo': False, 'separate_src': False, 'maven': False}
        self.assertEqual(opts, expect)
        self.assertEqual(custom, {})

    def test_override(self):
        taginfo = {'extra': {}}

        override = {'src': True}
        opts, custom = repos.get_repo_opts(taginfo, override)

        expect = {'src': True, 'debuginfo': False, 'separate_src': False, 'maven': False}
        self.assertEqual(opts, expect)
        self.assertEqual(custom, override)

    def test_override_redundant(self):
        taginfo = {'extra': {}}

        override = {'src': False}  # default setting, shouldn't be reported as custom
        opts, custom = repos.get_repo_opts(taginfo, override)

        expect = {'src': False, 'debuginfo': False, 'separate_src': False, 'maven': False}
        self.assertEqual(opts, expect)
        self.assertEqual(custom, {})

    def test_pattern_debug(self):
        self.context.opts['DebuginfoTags'] = 'TAG*'
        taginfo = {'name': 'TAG123', 'extra': {}}

        opts, custom = repos.get_repo_opts(taginfo)

        expect = {'src': False, 'debuginfo': True, 'separate_src': False, 'maven': False}
        self.assertEqual(opts, expect)
        self.assertEqual(custom, {})

    def test_pattern_source(self):
        self.context.opts['SourceTags'] = 'TAG*'
        taginfo = {'name': 'TAG123', 'extra': {}}

        opts, custom = repos.get_repo_opts(taginfo)

        expect = {'src': True, 'debuginfo': False, 'separate_src': False, 'maven': False}
        self.assertEqual(opts, expect)
        self.assertEqual(custom, {})

    def test_pattern_separate_src(self):
        self.context.opts['SeparateSourceTags'] = 'TAG*'
        taginfo = {'name': 'TAG123', 'extra': {}}

        opts, custom = repos.get_repo_opts(taginfo)

        expect = {'src': False, 'debuginfo': False, 'separate_src': True, 'maven': False}
        self.assertEqual(opts, expect)
        self.assertEqual(custom, {})

    def test_pattern_nomatch(self):
        self.context.opts['DebuginfoTags'] = 'FOO*'
        self.context.opts['SourceTags'] = 'FOO*'
        self.context.opts['SeparateSourceTags'] = 'FOO*'
        # this one shouldn't match
        taginfo = {'name': 'bar123', 'extra': {}}

        opts, custom = repos.get_repo_opts(taginfo)

        expect = {'src': False, 'debuginfo': False, 'separate_src': False, 'maven': False}
        self.assertEqual(opts, expect)
        self.assertEqual(custom, {})

    def test_tag_config(self):
        taginfo = {'extra': {'repo.opts': {'debuginfo': True}}}

        opts, custom = repos.get_repo_opts(taginfo)

        expect = {'src': False, 'debuginfo': True, 'separate_src': False, 'maven': False}
        self.assertEqual(opts, expect)
        self.assertEqual(custom, {})

        # old debuginfo should still work
        taginfo = {'extra': {'with_debuginfo': True}}
        opts, custom = repos.get_repo_opts(taginfo)
        expect = {'src': False, 'debuginfo': True, 'separate_src': False, 'maven': False}
        self.assertEqual(opts, expect)
        self.assertEqual(custom, {})

        # but repo.opts should win
        taginfo = {'extra': {'repo.opts': {}, 'with_debuginfo': True}}
        opts, custom = repos.get_repo_opts(taginfo)
        expect = {'src': False, 'debuginfo': False, 'separate_src': False, 'maven': False}
        self.assertEqual(opts, expect)
        self.assertEqual(custom, {})

    def test_old_maven(self):
        self.context.opts['EnableMaven'] = True
        taginfo = {'extra': {}, 'maven_support': True}

        opts, custom = repos.get_repo_opts(taginfo)

        expect = {'src': False, 'debuginfo': False, 'separate_src': False, 'maven': True}
        self.assertEqual(opts, expect)
        self.assertEqual(custom, {})

    def test_maven_disabled(self):
        self.context.opts['EnableMaven'] = False
        taginfo = {'extra': {}, 'maven_support': True}
        taginfo = {'extra': {'repo.opts': {'maven': True}, 'maven_support': True}}
        # should report maven=false regardless of other settings

        opts, custom = repos.get_repo_opts(taginfo)

        expect = {'src': False, 'debuginfo': False, 'separate_src': False, 'maven': False}
        self.assertEqual(opts, expect)
        self.assertEqual(custom, {})

    def test_maven_disabled_override(self):
        self.context.opts['EnableMaven'] = False
        taginfo = {'extra': {}}

        override = {'maven': True}
        opts, custom = repos.get_repo_opts(taginfo, override)

        # should report the override anyway
        expect = {'src': False, 'debuginfo': False, 'separate_src': False, 'maven': True}
        self.assertEqual(opts, expect)
        self.assertEqual(custom, override)


class TestConvertRepoOpts(BaseTest):

    def test_basic(self):
        value = {'debuginfo': False, 'src': True}
        # correctly formatted opts should not change
        opts = repos.convert_repo_opts(value)
        self.assertEqual(opts, value)

    def test_wrong_type(self):
        opts = repos.convert_repo_opts('STRING')
        self.assertEqual(opts, {})

        with self.assertRaises(koji.ParameterError):
            repos.convert_repo_opts('STRING', strict=True)

    def test_bad_key(self):
        bad = {'XYZ': True, 'src': True}
        opts = repos.convert_repo_opts(bad)
        self.assertEqual(opts, {'src': True})

        with self.assertRaises(koji.ParameterError):
            repos.convert_repo_opts(bad, strict=True)

    def test_null_value(self):
        value = {'debuginfo': None, 'src': True}
        opts = repos.convert_repo_opts(value)
        self.assertEqual(opts, {'src': True})


class TestRequestRepo(BaseTest):

    def setUp(self):
        super(TestRequestRepo, self).setUp()
        self.get_repo = mock.patch('kojihub.repos.get_repo').start()
        self.set_request_priority = mock.patch('kojihub.repos.set_request_priority').start()

    def test_basic_request(self):
        self.get_tag.return_value = {'id': 100, 'name': 'TAG', 'extra': {}}
        self.getLastEvent.return_value = {'id': 101010}
        self.tag_last_change_event.return_value = 100000
        repos.request_repo('TAGID')

    def test_request_last(self):
        self.get_tag.return_value = {'id': 100, 'name': 'TAG', 'extra': {}}
        self.getLastEvent.return_value = {'id': 101010}
        last = 100001
        self.tag_last_change_event.return_value = last
        self.get_repo.return_value = None
        self.RepoQueueQuery.return_value.execute.return_value = []

        repos.request_repo('TAGID', min_event="last")

        # check all the calls made with the value
        self.get_repo.assert_called_once()
        ev = self.get_repo.call_args.kwargs['min_event']
        self.assertEqual(ev, last)
        clauses = self.RepoQueueQuery.call_args_list[0].args[0]
        self.assertIn(['min_event', '>=', last], clauses)
        self.InsertProcessor.assert_called_once()
        data = self.InsertProcessor.call_args.kwargs['data']
        self.assertEqual(data['min_event'], last)

    def test_request_priority(self):
        self.get_tag.return_value = {'id': 100, 'name': 'TAG', 'extra': {}}
        ev = 100001
        self.get_repo.return_value = None
        self.RepoQueueQuery.return_value.execute.return_value = []

        repos.request_repo('TAGID', min_event=ev, priority=5)

        # check all the calls made with the value
        self.InsertProcessor.assert_called_once()
        data = self.InsertProcessor.call_args.kwargs['data']
        self.assertEqual(data['min_event'], ev)
        self.assertEqual(data['priority'], 25)  # default + 5

    def test_request_priority_lower_than_existing(self):
        self.get_tag.return_value = {'id': 100, 'name': 'TAG', 'extra': {}}
        ev = 100001
        self.get_repo.return_value = None
        oldreq = {'priority': 20, 'id': 424242}  # default
        self.RepoQueueQuery.return_value.execute.return_value = [oldreq]

        ret = repos.request_repo('TAGID', min_event=ev, priority=5)

        # we should return the existing entry
        # we should not update the priority since it is higher
        self.assertEqual(ret['request']['id'], 424242)
        self.assertEqual(ret['request']['priority'], 20)
        self.assertEqual(ret['duplicate'], True)
        self.InsertProcessor.assert_not_called()
        self.set_request_priority.assert_not_called()

    def test_request_priority_higher_not_allowed(self):
        self.context.session.hasPerm.return_value = False

        with self.assertRaises(koji.ActionNotAllowed):
            repos.request_repo('TAGID', min_event=101010, priority=-5)

        self.get_repo.assert_not_called()
        self.InsertProcessor.assert_not_called()
        self.set_request_priority.assert_not_called()

    def test_request_priority_higher_than_existing(self):
        self.get_tag.return_value = {'id': 100, 'name': 'TAG', 'extra': {}}
        ev = 100001
        self.get_repo.return_value = None
        oldreq = {'priority': 20, 'id': 424242}  # default
        self.RepoQueueQuery.return_value.execute.return_value = [oldreq]

        ret = repos.request_repo('TAGID', min_event=ev, priority=-5)

        # we should return the existing entry
        # we should update the priority
        self.assertEqual(ret['request']['id'], 424242)
        self.assertEqual(ret['request']['priority'], 15)
        self.assertEqual(ret['duplicate'], True)
        self.InsertProcessor.assert_not_called()
        self.set_request_priority.assert_called_once_with(424242, 15)

    def test_maven_disabled(self):
        self.context.opts['EnableMaven'] = False
        self.get_tag.return_value = {'id': 100, 'name': 'TAG', 'extra': {}}

        with self.assertRaises(koji.GenericError):
            repos.request_repo('TAGID', opts={'maven': True})

        self.InsertProcessor.assert_not_called()
        self.get_repo.assert_not_called()

    def test_event_conflict(self):
        self.get_tag.return_value = {'id': 100, 'name': 'TAG', 'extra': {}}

        with self.assertRaises(koji.ParameterError):
            repos.request_repo('TAGID', min_event=100, at_event=101)

        self.InsertProcessor.assert_not_called()
        self.get_repo.assert_not_called()

    def test_bad_at_event(self):
        self.get_tag.return_value = {'id': 100, 'name': 'TAG', 'extra': {}}
        self.getEvent.return_value = None

        with self.assertRaises(koji.ParameterError):
            repos.request_repo('TAGID', at_event=101)

        self.InsertProcessor.assert_not_called()
        self.get_repo.assert_not_called()
        self.getEvent.assert_called_once_with(101, strict=False)

    def test_bad_min_event(self):
        self.get_tag.return_value = {'id': 100, 'name': 'TAG', 'extra': {}}
        self.getEvent.return_value = None

        with self.assertRaises(koji.ParameterError):
            repos.request_repo('TAGID', min_event=101)

        self.InsertProcessor.assert_not_called()
        self.get_repo.assert_not_called()
        self.getEvent.assert_called_once_with(101, strict=False)

    def test_request_existing_repo(self):
        # if a matching repo exists, we should return it
        self.get_repo.return_value = 'MY-REPO'
        self.get_tag.return_value = {'id': 100, 'name': 'TAG', 'extra': {}}

        result = repos.request_repo('TAGID', min_event=101010)

        self.assertEqual(result['repo'], 'MY-REPO')
        self.get_repo.assert_called_with(100, min_event=101010, at_event=None, opts={})
        self.RepoQueueQuery.assert_not_called()
        self.nextval.assert_not_called()
        self.assertEqual(self.inserts, [])

    def test_request_existing_req(self):
        # if a matching request exists, we should return it
        self.get_tag.return_value = {'id': 100, 'name': 'TAG', 'extra': {}}
        self.get_repo.return_value = None
        req = {'repo_id': None, 'priority': 20, 'sentinel': 'hello'}
        self.RepoQueueQuery.return_value.execute.return_value = [req]

        result = repos.request_repo('TAG', min_event=101010)

        self.assertEqual(result['request'], req)
        self.get_repo.assert_called_with(100, min_event=101010, at_event=None, opts={})
        self.RepoQueueQuery.assert_called_once()
        expect = [['tag_id', '=', 100],
                  ['active', 'IS', True],
                  ['opts', '=', '{}'],
                  ['min_event', '>=', 101010]]
        clauses = self.RepoQueueQuery.mock_calls[0][1][0]
        self.assertEqual(clauses, expect)
        self.nextval.assert_not_called()
        self.assertEqual(self.inserts, [])

    def test_request_new_req(self):
        # if a matching request exists, we should return it
        self.get_tag.return_value = {'id': 100, 'name': 'TAG', 'extra': {}}
        self.get_repo.return_value = None
        self.RepoQueueQuery.return_value.execute.return_value = []
        self.RepoQueueQuery.return_value.executeOne.return_value = 'NEW-REQ'
        self.nextval.return_value = 'NEW-ID'
        self.context.session.user_id = 'USER'

        result = repos.request_repo('TAG', min_event=101010)

        self.get_repo.assert_called_with(100, min_event=101010, at_event=None, opts={})
        self.assertEqual(len(self.inserts), 1)
        expect = {
            'id': 'NEW-ID',
            'owner': 'USER',
            'priority': 20,
            'tag_id': 100,
            'at_event': None,
            'min_event': 101010,
            'opts': '{}',
        }
        self.assertEqual(self.inserts[0].data, expect)
        self.assertEqual(self.RepoQueueQuery.call_count, 2)
        # clauses for final query
        clauses = self.RepoQueueQuery.call_args[1]['clauses']
        self.assertEqual(clauses, [['id', '=', 'NEW-ID']])
        self.assertEqual(result['request'], 'NEW-REQ')

    def test_request_at_event(self):
        # similate an at_event request that finds an existing matching request to return
        self.get_tag.return_value = {'id': 100, 'name': 'TAG', 'extra': {}}
        self.get_repo.return_value = None
        req = {'repo_id': None, 'priority': 20, 'sentinel': 'hello'}
        self.RepoQueueQuery.return_value.execute.return_value = [req]

        result = repos.request_repo('TAG', at_event=101010)

        self.assertEqual(result['request'], req)
        self.get_repo.assert_called_with(100, min_event=None, at_event=101010, opts={})
        self.RepoQueueQuery.assert_called_once()
        expect = [['tag_id', '=', 100],
                  ['active', 'IS', True],
                  ['opts', '=', '{}'],
                  ['at_event', '=', 101010]]
        clauses = self.RepoQueueQuery.mock_calls[0][1][0]
        self.assertEqual(clauses, expect)
        self.nextval.assert_not_called()
        self.assertEqual(self.inserts, [])


class TestDefaultMinEvent(BaseTest):

    def setUp(self):
        super(TestDefaultMinEvent, self).setUp()
        self.time = mock.patch('time.time').start()

    def test_simple_lag(self):
        now = 1717171717
        self.time.return_value = now
        self.context.opts['RepoLag'] = 3600
        self.context.opts['RepoLagWindow'] = 1
        taginfo = {'id': 55, 'name': 'MYTAG', 'extra': {}}  # no lag override
        self.tag_last_change_event.return_value = 10000
        self.getLastEvent.return_value = {'id': 9999}

        ev = repos.default_min_event(taginfo)

        # we should report the ts from the last event, minus lag
        self.assertEqual(ev, 9999)
        self.getLastEvent.assert_called_once()
        base_ts = self.getLastEvent.call_args.kwargs['before']
        self.assertEqual(base_ts, now - 3600)

    def test_tag_older(self):
        now = 1717171717
        self.time.return_value = now
        self.context.opts['RepoLag'] = 3600
        self.context.opts['RepoLagWindow'] = 1
        taginfo = {'id': 55, 'name': 'MYTAG', 'extra': {}}  # no lag override
        self.tag_last_change_event.return_value = 9900
        self.getLastEvent.return_value = {'id': 9999}

        ev = repos.default_min_event(taginfo)

        # we should report the ts for the tag, since it is older
        self.assertEqual(ev, 9900)
        self.getLastEvent.assert_called_once()
        base_ts = self.getLastEvent.call_args.kwargs['before']
        self.assertEqual(base_ts, now - 3600)

    def test_window(self):
        now = 1717171717
        self.time.return_value = now
        self.context.opts['RepoLag'] = 3600
        self.context.opts['RepoLagWindow'] = 300
        taginfo = {'id': 55, 'name': 'MYTAG', 'extra': {}}  # no lag override
        self.tag_last_change_event.return_value = 9900
        self.getLastEvent.return_value = {'id': 9999}

        ev = repos.default_min_event(taginfo)

        # we should report the ts for the tag, since it is older
        self.assertEqual(ev, 9900)
        self.getLastEvent.assert_called_once()
        base_ts = self.getLastEvent.call_args.kwargs['before']
        # should be earlier than target time, but within lag window
        lag_ts = now - 3600
        if base_ts > lag_ts or base_ts < lag_ts - 600:
            raise Exception('Invalid lag window calculation')

    def test_lag_override(self):
        now = 1717171717
        self.time.return_value = now
        self.context.opts['RepoLag'] = 3600
        self.context.opts['RepoLagWindow'] = 1
        taginfo = {'id': 55, 'name': 'MYTAG', 'extra': {'repo.lag': 1800}}
        self.tag_last_change_event.return_value = 10000
        self.getLastEvent.return_value = {'id': 9999}

        ev = repos.default_min_event(taginfo)

        # we should report the ts from the last event, minus lag
        self.assertEqual(ev, 9999)
        self.getLastEvent.assert_called_once()
        base_ts = self.getLastEvent.call_args.kwargs['before']
        self.assertEqual(base_ts, now - 1800)

    def test_lag_override_invalid(self):
        now = 1717171717
        self.time.return_value = now
        self.context.opts['RepoLag'] = 3600
        self.context.opts['RepoLagWindow'] = 1
        taginfo = {'id': 55, 'name': 'MYTAG', 'extra': {'repo.lag': 'not an int'}}
        self.tag_last_change_event.return_value = 10000
        self.getLastEvent.return_value = {'id': 9999}

        ev = repos.default_min_event(taginfo)

        # we should report the ts from the last event, minus lag
        self.assertEqual(ev, 9999)
        self.getLastEvent.assert_called_once()
        base_ts = self.getLastEvent.call_args.kwargs['before']
        self.assertEqual(base_ts, now - 3600)

    def test_no_last_event(self):
        # corner case that can happen with very new instances
        now = 1717171717
        self.time.return_value = now
        taginfo = {'id': 55, 'name': 'MYTAG', 'extra': {}}
        self.tag_last_change_event.return_value = 10000
        self.getLastEvent.return_value = None
        self.tag_first_change_event.return_value = 9990

        ev = repos.default_min_event(taginfo)

        # in this corner case we should use the first event for the tag
        self.assertEqual(ev, 9990)
        self.getLastEvent.assert_called_once()
        self.tag_first_change_event.assert_called_once_with(55)


class TestCheckRequest(BaseTest):

    def setUp(self):
        super(TestCheckRequest, self).setUp()
        self.repo_info = mock.patch('kojihub.kojihub.repo_info').start()
        self.Task = mock.patch('kojihub.kojihub.Task').start()

    def test_have_repo(self):
        req = {'repo_id': 'REPOID', 'task_id': 'TASKID'}
        self.RepoQueueQuery.return_value.executeOne.return_value = req
        self.repo_info.return_value = 'REPO'

        ret = repos.check_repo_request(99)

        self.RepoQueueQuery.assert_called_once()
        self.repo_info.assert_called_once_with('REPOID')
        expect = {'request': req, 'repo': 'REPO'}
        self.assertEqual(ret, expect)

    def test_have_task(self):
        req = {'repo_id': None, 'task_id': 'TASKID'}
        self.RepoQueueQuery.return_value.executeOne.return_value = req
        self.Task.return_value.getInfo.return_value = 'TASK'

        ret = repos.check_repo_request(99)

        self.RepoQueueQuery.assert_called_once()
        self.repo_info.assert_not_called()
        self.Task.assert_called_once_with('TASKID')
        expect = {'repo': None, 'request': req, 'task': 'TASK'}
        self.assertEqual(ret, expect)

    def test_no_match(self):
        self.RepoQueueQuery.return_value.executeOne.return_value = None

        with self.assertRaises(koji.GenericError):
            repos.check_repo_request(99)

        self.RepoQueueQuery.assert_called_once()
        self.repo_info.assert_not_called()
        self.Task.assert_not_called()


class TestSetPriority(BaseTest):

    def test_set_request_priority(self):
        repos.set_request_priority(99, 15)

        self.UpdateProcessor.assert_called_once()
        update = self.updates[0]
        self.assertEqual(update.data, {'priority': 15})
        self.assertEqual(update.values, {'id': 99})


class TestExports(BaseTest):

    def setUp(self):
        super(TestExports, self).setUp()
        self.set_request_priority = mock.patch('kojihub.repos.set_request_priority').start()
        self.RepoQuery = mock.patch('kojihub.repos.RepoQuery').start()
        self.set_external_repo_data = mock.patch('kojihub.repos.set_external_repo_data').start()
        self.do_auto_requests = mock.patch('kojihub.repos.do_auto_requests').start()
        self.check_repo_queue = mock.patch('kojihub.repos.check_repo_queue').start()
        self.RepoQueueQuery = mock.patch('kojihub.repos.RepoQueueQuery').start()
        self.update_end_events = mock.patch('kojihub.repos.update_end_events').start()
        self.repo_references = mock.patch('kojihub.kojihub.repo_references').start()
        self.repo_set_state = mock.patch('kojihub.kojihub.repo_set_state').start()
        self.exports = repos.RepoExports()
        self.assertPerm = mock.MagicMock()
        self.context.session.assertPerm = self.assertPerm

    def test_no_perm(self):
        self.assertPerm.side_effect = koji.ActionNotAllowed('...')

        self.exports.references('REPO')
        self.exports.query('CLAUSES')
        self.exports.queryQueue('CLAUSES')

    def test_require_perm(self):
        self.assertPerm.side_effect = koji.ActionNotAllowed('...')

        with self.assertRaises(koji.ActionNotAllowed):
            self.exports.setRequestPriority(99, 1)
        self.set_request_priority.assert_not_called()
        self.assertEqual(self.assertPerm.call_args.args, ('admin',))

        with self.assertRaises(koji.ActionNotAllowed):
            self.exports.setState(99, 1)
        self.repo_set_state.assert_not_called()
        self.assertEqual(self.assertPerm.call_args.args, ('repo',))

        with self.assertRaises(koji.ActionNotAllowed):
            self.exports.setExternalRepoData(99, 1)
        self.set_external_repo_data.assert_not_called()
        self.assertEqual(self.assertPerm.call_args.args, ('repo',))

        with self.assertRaises(koji.ActionNotAllowed):
            self.exports.autoRequests()
        self.do_auto_requests.assert_not_called()
        self.assertEqual(self.assertPerm.call_args.args, ('repo',))

        with self.assertRaises(koji.ActionNotAllowed):
            self.exports.checkQueue()
        self.check_repo_queue.assert_not_called()
        self.assertEqual(self.assertPerm.call_args.args, ('repo',))

        with self.assertRaises(koji.ActionNotAllowed):
            self.exports.updateEndEvents()
        self.update_end_events.assert_not_called()
        self.assertEqual(self.assertPerm.call_args.args, ('repo',))

    def test_with_perm(self):
        # assertPerm does not raise
        self.exports.setRequestPriority(99, 1)
        self.exports.setState(99, 1)
        self.exports.setExternalRepoData(99, 1)
        self.exports.autoRequests()
        self.exports.checkQueue()
        self.exports.updateEndEvents()

# the end
