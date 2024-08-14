from __future__ import absolute_import
from unittest import mock
import os.path
import shutil
import tempfile
import time
import unittest

import koji

from . import loadkojira
kojira = loadkojira.kojira


class OurException(Exception):
    pass


class RepoManagerTest(unittest.TestCase):

    def setUp(self):
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.mgr = kojira.RepoManager(self.options, self.session)
        self.rmtree = mock.patch('koji.util.rmtree').start()
        # also mock in kojira namespace
        mock.patch.object(kojira, 'rmtree', new=self.rmtree).start()
        self.workdir = tempfile.mkdtemp()
        self.kill = mock.patch('os.kill').start()
        self.fork = mock.patch('os.fork').start()
        self.unlink = mock.patch('os.unlink').start()
        self.waitpid = mock.patch('os.waitpid', new=self.my_waitpid).start()
        # kojira defines global pathinfo in start block
        self.pathinfo = mock.patch.object(kojira, 'pathinfo', create=True).start()

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.workdir)

    def my_waitpid(self, pid, *a):
        # by default, report all processes exit normally
        return pid, 0

    @mock.patch('time.sleep')
    def test_regen_loop(self, sleep):
        subsession = mock.MagicMock()
        self.mgr.regenRepos = mock.MagicMock()
        self.mgr.regenRepos.side_effect = [None] * 10 + [OurException()]
        # we need the exception to terminate the infinite loop

        with self.assertRaises(OurException):
            self.mgr.regenLoop(subsession)

        self.assertEqual(self.mgr.regenRepos.call_count, 11)
        subsession.logout.assert_called_once()

    @mock.patch('time.sleep')
    def test_rmtree_loop(self, sleep):
        subsession = mock.MagicMock()
        self.mgr.checkQueue = mock.MagicMock()
        self.mgr.checkQueue.side_effect = [None] * 10 + [OurException()]
        # we need the exception to terminate the infinite loop

        with self.assertRaises(OurException):
            self.mgr.rmtreeLoop(subsession)

        self.assertEqual(self.mgr.checkQueue.call_count, 11)
        subsession.logout.assert_called_once()

    @mock.patch('time.sleep')
    def test_currency_loop(self, sleep):
        subsession = mock.MagicMock()
        subsession.repo.updateEndEvents.side_effect = [None] * 10 + [OurException()]
        # we need the exception to terminate the infinite loop

        with self.assertRaises(OurException):
            self.mgr.currencyChecker(subsession)

        self.assertEqual(subsession.repo.updateEndEvents.call_count, 11)
        subsession.logout.assert_called_once()

    @mock.patch('time.sleep')
    def test_external_loop(self, sleep):
        subsession = mock.MagicMock()
        self.mgr.checkExternalRepos = mock.MagicMock()
        self.mgr.checkExternalRepos.side_effect = [None] * 10 + [OurException()]
        # we need the exception to terminate the infinite loop

        with self.assertRaises(OurException):
            self.mgr.currencyExternalChecker(subsession)

        self.assertEqual(self.mgr.checkExternalRepos.call_count, 11)
        subsession.logout.assert_called_once()

    def test_rmtree(self):
        subsession = mock.MagicMock()
        dir1 = self.workdir + '/one'
        dir2 = self.workdir + '/two'
        self.assertEqual(list(self.mgr.delete_queue), [])

        # add a dir to the queue
        self.mgr.rmtree(dir1)
        self.assertEqual(list(self.mgr.delete_queue), [dir1])

        # duplicate should be ignored
        self.mgr.rmtree(dir1)
        self.assertEqual(list(self.mgr.delete_queue), [dir1])

        # new entry should appear in correct order
        self.mgr.rmtree(dir2)
        self.assertEqual(list(self.mgr.delete_queue), [dir1, dir2])

    def test_check_queue(self):
        self.options.max_delete_processes = 3
        nums = range(1, 11)  # 1 to 10
        # avoiding n=0 because we use it as a fake pid

        # queue up some deletes
        dirs = [self.workdir + '/dir_%02i' % n for n in nums]
        for d in dirs:
            self.mgr.rmtree(d)
        check = mock.MagicMock()
        self.rmtree.side_effect = [(n, check) for n in nums]
        # fake pids match dir number
        self.assertEqual(list(self.mgr.delete_queue), dirs)

        # first pass
        self.mgr.checkQueue()
        self.assertEqual(list(self.mgr.delete_queue), dirs[3:])
        self.assertEqual(set(self.mgr.delete_pids), set([1, 2, 3]))

        # second pass
        self.mgr.checkQueue()
        self.assertEqual(list(self.mgr.delete_queue), dirs[6:])
        self.assertEqual(set(self.mgr.delete_pids), set([4, 5, 6]))

        # third pass
        self.mgr.checkQueue()
        self.assertEqual(list(self.mgr.delete_queue), dirs[9:])
        self.assertEqual(set(self.mgr.delete_pids), set([7, 8, 9]))

        # fourth pass
        self.mgr.checkQueue()
        self.assertEqual(list(self.mgr.delete_queue), [])
        self.assertEqual(set(self.mgr.delete_pids), set([10]))

        # last pass
        self.mgr.checkQueue()
        self.assertEqual(list(self.mgr.delete_queue), [])
        self.assertEqual(set(self.mgr.delete_pids), set([]))

    def test_read_current(self):
        self.assertEqual(set(self.mgr.repos), set())

        # fake repo data
        data = {'create_event': 100, 'create_ts': 101010, 'tag_id': 999, 'state': 1,
                'dist': False, 'tag_name': 'TAG'}
        repo_ids = range(1000, 1015)
        repos = [dict(id=n, **data) for n in repo_ids]

        # pass 1
        self.session.repo.query.return_value = repos
        self.mgr.readCurrentRepos()

        self.assertEqual(set(self.mgr.repos), set([r['id'] for r in repos]))

        # pass 2 - no new repos
        self.mgr.readCurrentRepos()
        self.assertEqual(set(self.mgr.repos), set([r['id'] for r in repos]))

        # pass 3 - repo changes state
        repos[0] = repos[0].copy()  # don't change the data in mgr.repos
        repos[0]['state'] = 2  # expired
        repo_id = repos[0]['id']
        self.mgr.readCurrentRepos()
        self.assertEqual(set(self.mgr.repos), set([r['id'] for r in repos]))
        self.assertEqual(self.mgr.repos[repo_id].state, 2)
        self.assertEqual(self.mgr.repos[repo_id].data['state'], 2)

        # pass 4 - repo disappears from hub
        repos.pop(0)
        self.mgr.readCurrentRepos()
        self.assertEqual(set(self.mgr.repos), set([r['id'] for r in repos]))

    # using autospec so we can grab self from mock_calls
    @mock.patch.object(kojira.ManagedRepo, 'delete_check', autospec=True)
    def test_update_repos(self, delete_check):
        self.options.init_timeout = 3600
        self.options.repo_lifetime = 3600 * 24
        self.options.dist_repo_lifetime = 3600 * 24

        base_ts = 444888888

        # fake repo data
        data = {'tag_id': 999, 'state': koji.REPO_READY, 'tag_name': 'TAG', 'dist': False,
                'create_event': 100, 'end_event': 200, 'opts': {}, 'custom_opts': {},
                'state_ts': base_ts, 'creation_ts': base_ts}
        repo_ids = range(1000, 1015)
        repos = [dict(id=n, **data) for n in repo_ids]
        # make one old enough to expire
        repos[0]['state_ts'] = base_ts - self.options.repo_lifetime
        # make one stale
        repos[1]['state'] = koji.REPO_INIT
        repos[1]['creation_ts'] = base_ts - self.options.init_timeout
        # make one expired
        repos[2]['state'] = koji.REPO_EXPIRED

        # do the run
        self.session.repo.query.return_value = repos
        with mock.patch('time.time') as _time:
            _time.return_value = base_ts + 100  # shorter than all timeouts
            self.mgr.updateRepos()

        # confirm the expiration
        repo_id = repos[0]['id']
        self.session.repoExpire.assert_called_once_with(repo_id)
        self.assertEqual(self.mgr.repos[repo_id].state, koji.REPO_EXPIRED)
        self.assertEqual(self.mgr.repos[repo_id].data['state'], koji.REPO_EXPIRED)

        # confirm action on the stale repo
        repo_id = repos[1]['id']
        self.session.repoProblem.assert_called_once_with(repo_id)
        self.assertEqual(self.mgr.repos[repo_id].state, koji.REPO_PROBLEM)
        self.assertEqual(self.mgr.repos[repo_id].data['state'], koji.REPO_PROBLEM)

        # only repo 2 should have been checked for deletion
        repo_id = repos[2]['id']
        delete_check.assert_called_once()
        mrepo = delete_check.mock_calls[0][1][0]  # self arg
        self.assertEqual(mrepo.repo_id, repo_id)

    @mock.patch('requests.get')
    def test_check_external(self, get):
        # fake ext repo data
        repo1 = {'external_repo_id': 1, 'external_repo_name': 'myrepo',
                 'url': 'https://localhost/NOSUCHPATH'}
        repo2 = {'external_repo_id': 2, 'external_repo_name': 'myotherrepo',
                 'url': 'https://localhost/FAKEPATH/$arch'}
        self.session.getTagExternalRepos.return_value = [repo1, repo2]
        data1 = {}
        data2 = {}
        self.session.repo.getExternalRepoData.side_effect = [data1, data2]
        self.session.getAllArches.return_value = ['i386', 'x86_64', 'riscv']
        repomd_fn = os.path.dirname(__file__) + '/data/external-repomd.xml'
        with open(repomd_fn, 'rt') as fo:
            repomd = fo.read()
        get.return_value.text = repomd

        self.mgr.checkExternalRepos()

        self.session.repo.getExternalRepoData.assert_has_calls([
            mock.call(1),
            mock.call(2),
        ])
        self.session.repo.setExternalRepoData.assert_has_calls([
            mock.call(1, {'max_ts': 1711390493}),
            mock.call(2, {'max_ts': 1711390493}),
        ])

    @mock.patch('requests.get')
    def test_check_external_no_arches(self, get):
        # a new system with no hosts could report no arches
        self.session.getAllArches.return_value = []
        # fake ext repo data
        repo1 = {'external_repo_id': 1, 'external_repo_name': 'myrepo',
                 'url': 'https://localhost/NOSUCHPATH'}
        repo2 = {'external_repo_id': 2, 'external_repo_name': 'myotherrepo',
                 'url': 'https://localhost/FAKEPATH/$arch'}
        self.session.getTagExternalRepos.return_value = [repo1, repo2]
        data1 = {}
        data2 = {}
        self.session.repo.getExternalRepoData.side_effect = [data1, data2]
        repomd_fn = os.path.dirname(__file__) + '/data/external-repomd.xml'
        with open(repomd_fn, 'rt') as fo:
            repomd = fo.read()
        get.return_value.text = repomd

        self.mgr.checkExternalRepos()

        self.session.repo.getExternalRepoData.assert_has_calls([
            mock.call(1),
            # no call for repo2 since it has $arch in the url
        ])
        self.session.repo.setExternalRepoData.assert_has_calls([
            mock.call(1, {'max_ts': 1711390493}),
            # no call for repo2 since it has $arch in the url
        ])

    @mock.patch('requests.get')
    def test_check_external_cache(self, get):
        # fake ext repo data
        repo1 = {'external_repo_id': 1, 'external_repo_name': 'myrepo',
                 'url': 'https://localhost/NOSUCHPATH'}
        repo2 = {'external_repo_id': 2, 'external_repo_name': 'myotherrepo',
                 'url': 'https://localhost/NOSUCHPATH'}  # same url
        self.session.getTagExternalRepos.return_value = [repo1, repo2]
        data1 = {}
        data2 = {}
        self.session.repo.getExternalRepoData.side_effect = [data1, data2]
        self.session.getAllArches.return_value = ['i386', 'x86_64', 'riscv']
        repomd_fn = os.path.dirname(__file__) + '/data/external-repomd.xml'
        with open(repomd_fn, 'rt') as fo:
            repomd = fo.read()
        get.return_value.text = repomd

        self.mgr.checkExternalRepos()

        get.assert_called_once()
        self.session.repo.getExternalRepoData.assert_has_calls([
            mock.call(1),
            mock.call(2),
        ])
        self.session.repo.setExternalRepoData.assert_has_calls([
            mock.call(1, {'max_ts': 1711390493}),
            mock.call(2, {'max_ts': 1711390493}),
        ])

# the end
