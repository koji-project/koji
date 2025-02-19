from __future__ import absolute_import
try:
    from unittest import mock
except ImportError:
    import mock
import os
import rpm
import shutil
import tempfile
import unittest
import koji
import koji.tasks
from .loadkojid import kojid
from six.moves import range


class TestChooseTaskarch(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.options.copy_old_repodata = False
        self.options.createrepo_update = True
        self.topdir = self.tempdir + '/topdir'
        self.options.topdir = self.topdir
        self.pathinfo = koji.PathInfo(self.topdir)
        mock.patch('koji.pathinfo', new=self.pathinfo).start()

        # set up task handler
        task_id = 99
        method = 'newRepo'
        params = ['TAG']
        self.handler = kojid.NewRepoTask(task_id, method, params, self.session,
                self.options, self.tempdir + '/work')

        # mock some more things
        self.wait = mock.MagicMock()
        self.handler.wait = self.wait
        self.session.getExternalRepoList.return_value = []

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.tempdir)

    def test_basic(self):
        self.session.getTag.return_value = {'id': 'TAGID', 'name': 'TAG'}
        self.session.host.repoInit.return_value = ['REPOID', 'EVENTID']
        os.makedirs(self.topdir + '/repos/TAG/REPOID')
        arches = ['x86_64', 'aarch64']
        for arch in arches:
            os.makedirs(f'{self.topdir}/repos/TAG/REPOID/{arch}')
            # touch pkglist
            with open(f'{self.topdir}/repos/TAG/REPOID/{arch}/pkglist', 'wt') as fo:
                fo.write('fake-1.2.3-1.rpm\n')

        result = self.handler.run()

        self.assertEqual(result, ('REPOID', 'EVENTID'))
        self.assertEqual(len(self.session.host.subtask.mock_calls), 2)  # once per arch

    def test_no_dir_access(self):
        self.session.getTag.return_value = {'id': 'TAGID', 'name': 'TAG'}
        self.session.host.repoInit.return_value = ['REPOID', 'EVENTID']
        # we don't make the repos dir

        with self.assertRaises(koji.tasks.RefuseTask):
            result = self.handler.run()

        self.session.host.repoInit.assert_not_called()

    def test_oldrepo_no_update(self):
        taginfo = {'id': 'TAGID', 'name': 'TAG'}
        self.options.createrepo_update = False

        result = self.handler.get_old_repo(taginfo)

        self.assertEqual(result, (None, None))
        self.session.getRepo.assert_not_called()

    def test_oldrepo_no_update(self):
        taginfo = {'id': 'TAGID', 'name': 'TAG'}
        self.options.createrepo_update = False

        result = self.handler.get_old_repo(taginfo)

        self.assertEqual(result, (None, None))
        self.session.getRepo.assert_not_called()

    def test_oldrepo_simple(self):
        taginfo = {'id': 'TAGID', 'name': 'TAG'}
        repo = {'id': 'OLDREPOID', 'tag_id': 'TAGID'}
        self.session.getRepo.return_value = repo

        result = self.handler.get_old_repo(taginfo)

        self.assertEqual(result, (repo, self.topdir + '/repos/TAG/OLDREPOID'))
        self.session.getRepo.assert_called_once_with('TAGID')
        self.session.getFullInheritance.assert_not_called()

    def test_oldrepo_hint(self):
        taginfo = {'id': 'TAGID', 'name': 'TAG', 'extra': {'repo.oldrepo_hint': 'OTHERTAG'}}
        taginfo2 = {'id': 'TAGID2', 'name': 'OTHERTAG'}
        repo = {'id': 'OLDREPOID', 'tag_id': 'TAGID2'}
        self.session.getRepo.side_effect = [None, repo]
        self.session.getTag.return_value = taginfo2

        result = self.handler.get_old_repo(taginfo)

        self.assertEqual(result, (repo, self.topdir + '/repos/OTHERTAG/OLDREPOID'))
        expected_calls = [
            mock.call('TAGID'),
            mock.call('TAGID2'),
        ]
        self.assertEqual(self.session.getRepo.mock_calls, expected_calls)
        self.session.getFullInheritance.assert_not_called()

    def test_oldrepo_bad_hint(self):
        taginfo = {'id': 'TAGID', 'name': 'TAG',
                   'extra': {'repo.oldrepo_hint': ['BADTAG', 'OTHERTAG']}}
        taginfo2 = {'id': 'TAGID2', 'name': 'OTHERTAG'}
        repo = {'id': 'OLDREPOID', 'tag_id': 'TAGID2'}
        self.session.getRepo.side_effect = [None, repo]
        self.session.getTag.side_effect = [None, taginfo2]

        result = self.handler.get_old_repo(taginfo)

        self.assertEqual(result, (repo, self.topdir + '/repos/OTHERTAG/OLDREPOID'))
        expected_calls = [
            mock.call('TAGID'),
            mock.call('TAGID2'),
        ]
        self.assertEqual(self.session.getRepo.mock_calls, expected_calls)
        expected_calls = [
            mock.call('BADTAG', strict=False),
            mock.call('OTHERTAG', strict=False),
        ]
        self.assertEqual(self.session.getTag.mock_calls, expected_calls)
        self.session.getFullInheritance.assert_not_called()

    def test_oldrepo_inherit(self):
        taginfo = {'id': 'TAGID', 'name': 'TAG', 'extra': {}}
        taginfo2 = {'id': 'PARENTID', 'name': 'PARENTTAG'}
        repo = {'id': 'OLDREPOID', 'tag_id': 'PARENTID'}
        self.session.getRepo.side_effect = [None, repo]
        self.session.getFullInheritance.return_value = [{'parent_id': 'PARENTID', 'currdepth': 1}]
        self.session.getTag.return_value = taginfo2

        result = self.handler.get_old_repo(taginfo)

        self.assertEqual(result, (repo, self.topdir + '/repos/PARENTTAG/OLDREPOID'))
        expected_calls = [
            mock.call('TAGID'),
            mock.call('PARENTID'),
        ]
        self.assertEqual(self.session.getRepo.mock_calls, expected_calls)
        self.session.getFullInheritance.assert_called_once()

    def test_oldrepo_no_match(self):
        taginfo = {'id': 'TAGID', 'name': 'TAG', 'extra': {'repo.oldrepo_hint': 'OTHERTAG'}}
        taginfo2 = {'id': 'TAGID2', 'name': 'OTHERTAG'}
        self.session.getRepo.return_value = None
        self.session.getFullInheritance.return_value = [{'parent_id': 'PARENTID', 'currdepth': 1}]
        self.session.getTag.return_value = taginfo2

        result = self.handler.get_old_repo(taginfo)

        self.assertEqual(result, (None, None))
        expected_calls = [
            mock.call('TAGID'),
            mock.call('TAGID2'),
            mock.call('PARENTID'),
        ]
        self.assertEqual(self.session.getRepo.mock_calls, expected_calls)
        self.session.getFullInheritance.assert_called_once()
# the end
