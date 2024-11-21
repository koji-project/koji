from __future__ import absolute_import
import json
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


class ManagedRepoTest(unittest.TestCase):

    def setUp(self):
        self.workdir = tempfile.mkdtemp()
        self.kojidir = self.workdir + '/koji'
        os.mkdir(self.kojidir)
        self.pathinfo = koji.PathInfo(self.kojidir)
        mock.patch.object(kojira, 'pathinfo', new=self.pathinfo, create=True).start()

        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.mgr = mock.MagicMock()
        self.mgr.options = self.options
        self.mgr.session = self.session
        self.unlink = mock.patch('os.unlink').start()
        self.data = {
            'create_event': 497359,
            'create_ts': 1709791593.368943,
            'creation_ts': 1709791593.367575,
            'dist': False,
            'end_event': None,
            'id': 2385,
            'opts': {'debuginfo': False, 'separate_src': False, 'src': False},
            'custom_opts': {},
            'state': 1,
            'state_ts': 1710705227.166751,
            'tag_id': 50,
            'tag_name': 'some-tag',
            'task_id': 13290,
        }
        self.repo = self.mkrepo(self.data)

    def mkrepo(self, data):
        repodir = self.kojidir + ('/repos/%(tag_name)s/%(id)s' % self.data)
        os.makedirs(repodir)
        with open('%s/repo.json' % repodir, 'wt', encoding='utf-8') as fp:
            # technically not quite the right data, but close enough
            json.dump(data, fp, indent=2)
        for arch in ('x86_64', 'aarch64'):
            os.mkdir(repodir + '/' + arch)
        repo = kojira.ManagedRepo(self.mgr, data.copy())
        return repo

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.workdir)

    def test_get_info(self):
        info = self.repo.get_info()
        self.assertEqual(info, self.data)

    def test_get_path(self):
        path = self.repo.get_path()
        repodir = self.kojidir + ('/repos/%(tag_name)s/%(id)s' % self.repo.data)
        self.assertEqual(path, repodir)

    def test_delete_check(self):
        self.options.expired_repo_lifetime = 3600 * 24
        self.options.reference_recheck_period = 3600
        base_ts = 444888888
        now = base_ts + 100

        self.repo.data['state'] = koji.REPO_EXPIRED
        self.repo.data['state_ts'] = base_ts

        with mock.patch('time.time') as _time:
            _time.return_value = now
            self.repo.delete_check()

        # we should have stopped at the age check
        self.session.repo.references.assert_not_called()
        self.mgr.rmtree.assert_not_called()
        path = self.repo.get_path()
        if not os.path.exists(path):
            raise Exception('Missing directory: %s' % path)

        # try again with later time but also references
        now += self.options.expired_repo_lifetime
        self.session.repo.references.return_value = ['REF1', 'REF2']
        with mock.patch('time.time') as _time:
            _time.return_value = now
            self.repo.delete_check()

        self.mgr.rmtree.assert_not_called()
        path = self.repo.get_path()
        if not os.path.exists(path):
            raise Exception('Missing directory: %s' % path)

        self.session.reset_mock()

        # no refs, but same time as last check
        # (now unchanged)
        self.session.repo.references.return_value = []
        with mock.patch('time.time') as _time:
            _time.return_value = now
            self.repo.delete_check()

        # we should have stopped at the recheck_period check
        self.session.repo.references.assert_not_called()
        self.mgr.rmtree.assert_not_called()

        # finally, let's check again with no refs
        now += self.options.reference_recheck_period
        with mock.patch('time.time') as _time:
            _time.return_value = now
            self.repo.delete_check()

        self.session.repo.setState.assert_called_once_with(self.repo.id, koji.REPO_DELETED)
        self.mgr.rmtree.assert_called_once_with(path)

    def test_expire_check_recent(self):
        self.options.repo_lifetime = 3600 * 24
        self.options.recheck_period = 3600
        base_ts = 444888888
        now = base_ts + 100

        self.repo.data['state'] = koji.REPO_READY
        self.repo.data['state_ts'] = base_ts
        self.repo.data['end_event'] = 999

        with mock.patch('time.time') as _time:
            _time.return_value = now
            self.repo.expire_check()

        # we should have stopped at the age check
        self.session.getBuildTargets.assert_not_called()
        self.session.repoExpire.assert_not_called()

    def test_expire_check_recheck(self):
        self.options.repo_lifetime = 3600 * 24
        self.options.recheck_period = 3600
        base_ts = 444888888
        now = base_ts + self.options.repo_lifetime + 100

        # recheck period still in effect
        self.repo.expire_check_ts = now - 3500
        # otherwise eligible to expire
        self.repo.data['state'] = koji.REPO_READY
        self.repo.data['state_ts'] = base_ts
        self.repo.data['end_event'] = 999

        with mock.patch('time.time') as _time:
            _time.return_value = now
            self.repo.expire_check()

        self.session.getBuildTargets.assert_not_called()
        self.session.repo.query.assert_not_called()
        self.session.repoExpire.assert_not_called()

    def test_expire_check_latest(self):
        self.options.repo_lifetime = 3600 * 24
        self.options.recheck_period = 3600
        base_ts = 444888888
        now = base_ts + self.options.repo_lifetime + 100

        self.repo.data['state'] = koji.REPO_READY
        self.repo.data['state_ts'] = base_ts
        self.repo.data['end_event'] = 999
        # latest for a target, should not get expired
        self.session.getBuildTargets.return_value = ['TARGET']
        self.session.repo.query.return_value = []

        with mock.patch('time.time') as _time:
            _time.return_value = now
            self.repo.expire_check()

        self.session.getBuildTargets.assert_called_once()
        self.session.repo.query.assert_called_once()
        self.session.repoExpire.assert_not_called()

    def test_expire_check_expire(self):
        self.options.repo_lifetime = 3600 * 24
        self.options.recheck_period = 3600
        base_ts = 444888888
        now = base_ts + self.options.repo_lifetime + 100

        self.repo.data['state'] = koji.REPO_READY
        self.repo.data['state_ts'] = base_ts
        self.repo.data['end_event'] = 999
        # not latest
        self.session.getBuildTargets.return_value = ['TARGET']
        self.session.repo.query.return_value = ['NEWER_REPO']

        with mock.patch('time.time') as _time:
            _time.return_value = now
            self.repo.expire_check()

        self.session.getBuildTargets.assert_called_once()
        self.session.repo.query.assert_called_once()
        self.session.repoExpire.assert_called_once()


# the end
