import mock

import unittest

import koji.tasks
from koji.util import RepoWatcher


class TestRepoWatcher(unittest.TestCase):

    TAG = {'id': 137, 'name': 'MY-TAG'}

    def setUp(self):
        self.session = mock.MagicMock()
        self.checkForBuilds = mock.patch('koji.util.checkForBuilds').start()
        self.session.getTag.return_value = self.TAG
        self.sleep = mock.patch('time.sleep').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_getRepo_ready(self):
        repoinfo = {'id': 123, 'tag_id': self.TAG['id']}
        self.session.repo.request.return_value = {'repo': repoinfo}
        watcher = RepoWatcher(self.session, 'TAG')
        result = watcher.getRepo()
        self.assertEqual(result, repoinfo)

    def test_getRepo_request(self):
        self.session.repo.request.return_value = {'repo': None, 'request': {'id': 999}}
        watcher = RepoWatcher(self.session, 'TAG')
        result = watcher.getRepo()
        self.assertEqual(result, None)

    def test_getRepo_builds_missing(self):
        self.session.repo.request.return_value = {'repo': None, 'request': {'id': 999}}
        self.checkForBuilds.return_value = False
        watcher = RepoWatcher(self.session, 'TAG', nvrs=['package-1.2-34'])
        result = watcher.getRepo()
        self.assertEqual(result, None)
        self.checkForBuilds.assert_called_once()

    def test_waitrepo_request_gives_repo(self):
        repoinfo = {'id': 123, 'tag_id': self.TAG['id']}
        self.session.repo.get.return_value = None
        self.session.repo.request.return_value = {'repo': repoinfo}
        watcher = RepoWatcher(self.session, 'TAG')
        result = watcher.waitrepo()
        self.assertEqual(result, repoinfo)

    def test_waitrepo_request_wait(self):
        repoinfo = {'id': 123, 'tag_id': self.TAG['id']}
        req = {'id': 999, 'min_event': 10001, 'task_id': 'TASK', 'task_state': 0, 'repo_id': None,
               'active': True, 'tries': 1}
        self.session.repo.get.return_value = None
        check = {'repo': None, 'request': req}
        req2 = req.copy()
        req2['task_state'] = 1
        check2 = {'repo': None, 'request': req2}
        self.session.repo.request.return_value = check
        done = {'repo': repoinfo, 'request': req}
        self.session.repo.checkRequest.side_effect = [check, check, check2, done]
        watcher = RepoWatcher(self.session, 'TAG')
        result = watcher.waitrepo()
        self.assertEqual(result, repoinfo)

    def test_waitrepo_anon_wait(self):
        repoinfo = {'id': 123, 'tag_id': self.TAG['id']}
        self.session.repo.get.side_effect = [None] * 5 + [repoinfo]
        watcher = RepoWatcher(self.session, 'TAG')
        result = watcher.waitrepo(anon=True)
        self.assertEqual(result, repoinfo)
        self.session.repo.request.assert_not_called()

    def test_waitrepo_request_timeout(self):
        req = {'id': 999, 'min_event': 10001, 'task_id': 'TASK', 'task_state': 0, 'repo_id': None,
               'active': True, 'tries': 1}
        self.session.repo.get.return_value = None
        check = {'repo': None, 'request': req}
        self.session.repo.request.return_value = check
        self.session.repo.checkRequest.side_effect = [check] * 20
        watcher = RepoWatcher(self.session, 'TAG')
        watcher.check_timeout = mock.MagicMock()
        watcher.check_timeout.side_effect = [False] * 10 + [True]
        with self.assertRaises(koji.GenericError) as err:
            watcher.waitrepo()

    def test_taskargs(self):
        watcher = RepoWatcher(self.session, 'TAG')
        args = watcher.task_args()
        params = koji.tasks.parse_task_params('waitrepo', args)

    def test_waitrepo_build_wait(self):
        self.session.repo.get.return_value = None
        # we'll pass with nvrs, so we should wait for builds before making request
        nvrs = ['package-1.2-34']
        builds = [{'name': 'package', 'version': '1.2', 'release': '34', 'epoch': ''}]
        self.session.tagLastChangeEvent.return_value = 10000

        def got_builds():
            # called when we start reporting the builds in the tag
            self.session.repo.request.assert_not_called()
            self.session.tagLastChangeEvent.return_value = 10002
            return True

        self.checkForBuilds.side_effect = [False, False, False, got_builds, True]
        # once we report the build, checkForBuilds should be called just once more to verify the repo

        req = {'id': 999, 'min_event': 10000, 'task_id': 'TASK', 'task_state': 0, 'repo_id': None,
               'active': True, 'tries': 1}
        check = {'repo': None, 'request': req}
        self.session.repo.request.return_value = check

        repoinfo = {'id': 123, 'tag_id': self.TAG['id'], 'create_event': 10002}
        done = {'repo': repoinfo, 'request': req}
        self.session.repo.checkRequest.side_effect = [check, check, check, done]

        watcher = RepoWatcher(self.session, 'TAG', nvrs=nvrs)
        result = watcher.waitrepo()

        self.assertEqual(result, repoinfo)
        # checkForBuilds is called several times, the event arg can vary, but the others should not
        for call in self.checkForBuilds.mock_calls:
            # name, args, kwargs
            # session, tag, builds, event, latest
            self.assertEqual(call[1][0], self.session)
            self.assertEqual(call[1][1], self.TAG['id'])
            self.assertEqual(call[1][2], builds)

    def test_waitrepo_build_timeout(self):
        self.session.repo.get.return_value = None
        nvrs = ['package-1.2-34']
        # just keep reporting that the build is not there
        self.checkForBuilds.side_effect = [False] * 20

        watcher = RepoWatcher(self.session, 'TAG', nvrs=nvrs)
        watcher.check_timeout = mock.MagicMock()
        watcher.check_timeout.side_effect = [False] * 10 + [True]
        with self.assertRaises(koji.GenericError) as err:
            watcher.waitrepo()

        # we should not have reached the request stage
        self.session.repo.request.assert_not_called()

    def test_waitrepo_build_not_in_repo(self):
        self.session.repo.get.return_value = None
        nvrs = ['package-1.2-34']
        self.session.tagLastChangeEvent.return_value = 10000

        # replace checkForBuilds
        def my_check(session, tag, builds, event, latest=False):
            if event and event < 10002:
                # called from check_repo with repo event id
                return False
            return True

        self.checkForBuilds.side_effect = my_check

        req1 = {'id': 999, 'min_event': 10000, 'task_id': 'TASK', 'task_state': 0, 'repo_id': None}
        req2 = req1.copy()
        req2['min_event'] = 10002
        repo1 = {'id': 123, 'tag_id': self.TAG['id'], 'create_event': 10000}
        repo2 = {'id': 123, 'tag_id': self.TAG['id'], 'create_event': 10002}
        check1 = {'repo': None, 'request': req1}
        check1b = {'repo': repo1, 'request': req1}
        check2 = {'repo': None, 'request': req2}
        check2b = {'repo': repo2, 'request': req2}

        # request should be made twice
        self.session.repo.request.side_effect = [check1, check2]

        # and each checked once
        self.session.repo.checkRequest.side_effect = [check1b, check2b]

        watcher = RepoWatcher(self.session, 'TAG', nvrs=nvrs)
        result = watcher.waitrepo()

        self.assertEqual(result, repo2)

    def test_check_repo(self):
        watcher = RepoWatcher(self.session, 'TAG')
        repo = {'tag_id': self.TAG['id'], 'create_event': 10000, 'opts': {'src': True}}
        self.checkForBuilds.return_value = True

        # wrong tag
        _repo = repo.copy()
        _repo['tag_id'] += 1
        result = watcher.check_repo(_repo)
        self.assertEqual(result, False)

        # wrong at_event
        watcher = RepoWatcher(self.session, 'TAG', at_event=5000)
        result = watcher.check_repo(repo)
        self.assertEqual(result, False)

        # wrong min_event
        watcher = RepoWatcher(self.session, 'TAG', min_event=20000)
        result = watcher.check_repo(repo)
        self.assertEqual(result, False)

        # wrong opts
        watcher = RepoWatcher(self.session, 'TAG', opts={'src': False})
        result = watcher.check_repo(repo)
        self.assertEqual(result, False)

        # wrong builds
        nvrs = ['package-1.2-34']
        self.checkForBuilds.return_value = False
        watcher = RepoWatcher(self.session, 'TAG', nvrs=nvrs)
        result = watcher.check_repo(repo)
        self.assertEqual(result, False)

        # good
        self.checkForBuilds.return_value = True
        watcher = RepoWatcher(self.session, 'TAG', nvrs=nvrs, at_event=10000, opts={'src': True})
        result = watcher.check_repo(repo)
        self.assertEqual(result, True)

    def test_event_args(self):
        # both min and at
        with self.assertRaises(koji.ParameterError):
            watcher = RepoWatcher(self.session, 'TAG', min_event=100, at_event=99)

        self.session.tagLastChangeEvent.return_value = 101010
        watcher = RepoWatcher(self.session, 'TAG', min_event='last')
        self.assertEqual(watcher.min_event, 101010)
        self.session.tagLastChangeEvent.assert_called_once()




# the end
