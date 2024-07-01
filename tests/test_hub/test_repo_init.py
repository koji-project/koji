import json
import mock
import os
import shutil
import tempfile
import unittest

from xml.etree import ElementTree

import koji
import kojihub


IP = kojihub.InsertProcessor
QP = kojihub.QueryProcessor


class TestRepoInit(unittest.TestCase):

    def setUp(self):
        self.context = mock.MagicMock()
        self.context.opts = {
            'EnableMaven': False,
        }
        mock.patch('kojihub.repos.context', new=self.context).start()
        mock.patch('kojihub.kojihub.context', new=self.context).start()
        self.tempdir = tempfile.mkdtemp()
        self.pathinfo = koji.PathInfo(self.tempdir)
        mock.patch('koji.pathinfo', new=self.pathinfo).start()
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.taginfo = {'id': 137, 'name': 'TAG', 'arches': 'x86_64 aarch64', 'extra': {}}
        self.get_tag.return_value = self.taginfo
        self.readTaggedRPMS = mock.patch('kojihub.kojihub.readTaggedRPMS').start()
        self.readTaggedRPMS.return_value = [], []
        self.readTagGroups = mock.patch('kojihub.kojihub.readTagGroups').start()
        self.readPackageList = mock.patch('kojihub.kojihub.readPackageList').start()
        self.maven_tag_archives = mock.patch('kojihub.kojihub.maven_tag_archives').start()
        self.tag_first_change_event = mock.patch('kojihub.kojihub.tag_first_change_event').start()
        self.tag_last_change_event = mock.patch('kojihub.kojihub.tag_last_change_event').start()
        self.get_repo_opts = mock.patch('kojihub.repos.get_repo_opts').start()
        self.default_opts = {'src': False, 'debuginfo': False, 'separate_src': False,
                             'maven': False}
        self.get_repo_opts.return_value = self.default_opts, {}

        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_execute = mock.MagicMock()
        self.query_executeOne = mock.MagicMock()
        self.query_singleValue = mock.MagicMock()

        self.singleValue = mock.patch('kojihub.kojihub._singleValue').start()
        self.singleValue.return_value = 'EVENTID'
        self.nextval = mock.patch('kojihub.kojihub.nextval').start()
        self.nextval.return_value = 'REPOID'

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.tempdir)

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = self.query_execute
        query.executeOne = self.query_executeOne
        query.singleValue = self.query_singleValue
        self.queries.append(query)
        return query

    def test_repo_init_wrong_type_typeID(self):
        task_id = 'test-task_id'
        with self.assertRaises(koji.ParameterError) as cm:
            kojihub.repo_init('test-tag', task_id)
        self.assertEqual(f"Invalid type for value '{task_id}': {type(task_id)}, "
                         f"expected type <class 'int'>", str(cm.exception))

    def test_maven_disabled(self):
        self.context.opts['EnableMaven'] = False
        opts = dict(self.default_opts, maven=True)
        custom = {'maven': True}
        self.get_repo_opts.return_value = opts, custom
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.repo_init('test-tag', 100, opts=custom)
        self.assertEqual('Maven support not enabled', str(cm.exception))

    def test_empty_repo(self):
        # fairly trivial case of empty repo
        task_id = 100
        self.readTaggedRPMS.return_value = [], []
        kojihub.repo_init('test-tag', task_id)

        repodir = f'{self.tempdir}/repos/TAG/REPOID'
        expect = ['aarch64', 'groups', 'repo.json', 'x86_64']
        self.assertEqual(sorted(os.listdir(repodir)), expect)

        with open(f'{repodir}/repo.json', 'rt') as fo:
            info = json.load(fo)
        self.assertEqual(info['id'], 'REPOID')
        self.assertEqual(info['tag'], 'TAG')
        self.assertEqual(info['tag_id'], 137)
        self.assertEqual(info['task_id'], 100)
        self.assertEqual(info['event_id'], 'EVENTID')
        self.assertEqual(info['opts'], self.default_opts)
        self.assertEqual(info['custom_opts'], {})

        # basic comps check
        with open(f'{repodir}/groups/comps.xml', 'rt') as fo:
            root = ElementTree.fromstring(fo.read())

        for arch in ['x86_64', 'aarch64']:
            # contents
            expect = ['blocklist', 'pkglist', 'rpmlist.jsonl', 'toplink']
            self.assertEqual(sorted(os.listdir(f'{repodir}/{arch}')), expect)

            # check toplink
            if not os.path.samefile(f'{repodir}/{arch}/toplink', self.tempdir):
                raise Exception('invalid toplink')

            # pkglist should be blank
            with open(f'{repodir}/{arch}/pkglist', 'rt') as fo:
                self.assertEqual(fo.read(), '')

            # blocklist should be blank
            with open(f'{repodir}/{arch}/blocklist', 'rt') as fo:
                self.assertEqual(fo.read(), '')

            # rpmlist should be blank
            with open(f'{repodir}/{arch}/rpmlist.jsonl', 'rt') as fo:
                self.assertEqual(fo.read(), '')

    DATA1 = [
        [
            # srpm
            {
                'arch': 'src',
                'build_id': 575,
                'draft': False,
                'id': 6100,
                'name': 'mypackage',
                'release': '36',
                'version': '1.1',
            },
            # noarch
            {
                'arch': 'noarch',
                'build_id': 575,
                'draft': False,
                'id': 6101,
                'name': 'mypackage',
                'release': '36',
                'version': '1.1',
            },
            # x86_64
            {
                'arch': 'x86_64',
                'build_id': 575,
                'draft': False,
                'id': 6102,
                'name': 'mypackage-binary',
                'release': '36',
                'version': '1.1',
            },
            # alpha -- not in list
            {
                'arch': 'alpha',
                'build_id': 575,
                'draft': False,
                'id': 6103,
                'name': 'mypackage-binary',
                'release': '36',
                'version': '1.1',
            },
            # debuginfo
            {
                'arch': 'x86_64',
                'build_id': 575,
                'draft': False,
                'id': 6104,
                'name': 'mypackage-debuginfo',
                'release': '36',
                'version': '1.1',
            },
        ],
        # builds
        [
            {
                'draft': False,
                'id': 575,
                'name': 'mypackage',
                'nvr': 'mypackage-1.1-36',
                'package_id': 370,
                'package_name': 'mypackage',
                'release': '36',
                'source': 'mypackage-1.1-36.src.rpm',
                'state': 1,
                'version': '1.1',
                'volume_id': 0,
                'volume_name': 'DEFAULT',
            },
        ]
    ]

    def test_repo_with_rpms(self):
        task_id = 100
        rpms, builds = self.DATA1
        self.readTaggedRPMS.return_value = rpms, builds
        kojihub.repo_init('test-tag', task_id)

        repodir = f'{self.tempdir}/repos/TAG/REPOID'
        expect = ['aarch64', 'groups', 'repo.json', 'x86_64']
        self.assertEqual(sorted(os.listdir(repodir)), expect)

        with open(f'{repodir}/repo.json', 'rt') as fo:
            info = json.load(fo)
        self.assertEqual(info['id'], 'REPOID')
        self.assertEqual(info['tag'], 'TAG')
        self.assertEqual(info['tag_id'], 137)
        self.assertEqual(info['task_id'], 100)
        self.assertEqual(info['event_id'], 'EVENTID')
        self.assertEqual(info['opts'], self.default_opts)
        self.assertEqual(info['custom_opts'], {})

        # basic comps check
        with open(f'{repodir}/groups/comps.xml', 'rt') as fo:
            root = ElementTree.fromstring(fo.read())

        for arch in ['x86_64', 'aarch64']:
            # contents
            expect = ['blocklist', 'pkglist', 'rpmlist.jsonl', 'toplink']
            self.assertEqual(sorted(os.listdir(f'{repodir}/{arch}')), expect)

            # check toplink
            if not os.path.samefile(f'{repodir}/{arch}/toplink', self.tempdir):
                raise Exception('invalid toplink')

            # blocklist should be blank
            with open(f'{repodir}/{arch}/blocklist', 'rt') as fo:
                self.assertEqual(fo.read(), '')

            # check rpm contents
            arch_rpms = [r for r in rpms if r['arch'] in ('noarch', arch)
                            and 'debug' not in r['name']]
            with open(f'{repodir}/{arch}/rpmlist.jsonl', 'rt') as fo:
                repo_rpms = [json.loads(line) for line in fo]
                self.assertEqual(repo_rpms, arch_rpms)

            with open(f'{repodir}/{arch}/pkglist', 'rt') as fo:
                lines = fo.readlines()
                self.assertEqual(len(lines), len(arch_rpms))

    def test_separate_source(self):
        task_id = 100
        rpms, builds = self.DATA1
        self.readTaggedRPMS.return_value = rpms, builds
        opts = dict(self.default_opts, separate_src=True)
        custom = {'separate_src': True}
        self.get_repo_opts.return_value = opts, custom
        kojihub.repo_init('test-tag', task_id)

        repodir = f'{self.tempdir}/repos/TAG/REPOID'
        expect = ['aarch64', 'groups', 'repo.json', 'src', 'x86_64']
        self.assertEqual(sorted(os.listdir(repodir)), expect)

        with open(f'{repodir}/repo.json', 'rt') as fo:
            info = json.load(fo)
        self.assertEqual(info['id'], 'REPOID')
        self.assertEqual(info['tag'], 'TAG')
        self.assertEqual(info['tag_id'], 137)
        self.assertEqual(info['task_id'], 100)
        self.assertEqual(info['event_id'], 'EVENTID')
        self.assertEqual(info['opts'], opts)
        self.assertEqual(info['custom_opts'], custom)

        # basic comps check
        with open(f'{repodir}/groups/comps.xml', 'rt') as fo:
            root = ElementTree.fromstring(fo.read())

        for arch in ['x86_64', 'aarch64', 'src']:
            # contents
            expect = ['blocklist', 'pkglist', 'rpmlist.jsonl', 'toplink']
            self.assertEqual(sorted(os.listdir(f'{repodir}/{arch}')), expect)

            # check toplink
            if not os.path.samefile(f'{repodir}/{arch}/toplink', self.tempdir):
                raise Exception('invalid toplink')

            # blocklist should be blank
            with open(f'{repodir}/{arch}/blocklist', 'rt') as fo:
                self.assertEqual(fo.read(), '')

            # check rpm contents
            # srpms go only into src repo
            if arch == 'src':
                arch_rpms = [r for r in rpms if r['arch'] == 'src']
            else:
                arch_rpms = [r for r in rpms if r['arch'] in ('noarch', arch)
                                and 'debug' not in r['name']]
            with open(f'{repodir}/{arch}/rpmlist.jsonl', 'rt') as fo:
                repo_rpms = [json.loads(line) for line in fo]
                self.assertEqual(repo_rpms, arch_rpms)

            with open(f'{repodir}/{arch}/pkglist', 'rt') as fo:
                lines = fo.readlines()
                self.assertEqual(len(lines), len(arch_rpms))

    def test_with_src(self):
        task_id = 100
        rpms, builds = self.DATA1
        self.readTaggedRPMS.return_value = rpms, builds
        opts = dict(self.default_opts, src=True)
        custom = {'src': True}
        self.get_repo_opts.return_value = opts, custom
        kojihub.repo_init('test-tag', task_id)

        repodir = f'{self.tempdir}/repos/TAG/REPOID'
        expect = ['aarch64', 'groups', 'repo.json', 'x86_64']
        self.assertEqual(sorted(os.listdir(repodir)), expect)

        with open(f'{repodir}/repo.json', 'rt') as fo:
            info = json.load(fo)
        self.assertEqual(info['id'], 'REPOID')
        self.assertEqual(info['tag'], 'TAG')
        self.assertEqual(info['tag_id'], 137)
        self.assertEqual(info['task_id'], 100)
        self.assertEqual(info['event_id'], 'EVENTID')
        self.assertEqual(info['opts'], opts)
        self.assertEqual(info['custom_opts'], custom)

        # basic comps check
        with open(f'{repodir}/groups/comps.xml', 'rt') as fo:
            root = ElementTree.fromstring(fo.read())

        for arch in ['x86_64', 'aarch64']:
            # contents
            expect = ['blocklist', 'pkglist', 'rpmlist.jsonl', 'toplink']
            self.assertEqual(sorted(os.listdir(f'{repodir}/{arch}')), expect)

            # check toplink
            if not os.path.samefile(f'{repodir}/{arch}/toplink', self.tempdir):
                raise Exception('invalid toplink')

            # blocklist should be blank
            with open(f'{repodir}/{arch}/blocklist', 'rt') as fo:
                self.assertEqual(fo.read(), '')

            # check rpm contents
            # all arch repos get noarch AND src
            arch_rpms = [r for r in rpms if r['arch'] in ('noarch', 'src', arch)
                            and 'debug' not in r['name']]
            with open(f'{repodir}/{arch}/rpmlist.jsonl', 'rt') as fo:
                repo_rpms = [json.loads(line) for line in fo]
                self.assertEqual(repo_rpms, arch_rpms)

            with open(f'{repodir}/{arch}/pkglist', 'rt') as fo:
                lines = fo.readlines()
                self.assertEqual(len(lines), len(arch_rpms))

    def test_repo_with_debuginfo(self):
        task_id = 100
        rpms, builds = self.DATA1
        self.readTaggedRPMS.return_value = rpms, builds
        opts = dict(self.default_opts, debuginfo=True)
        custom = {'debuginfo': True}
        self.get_repo_opts.return_value = opts, custom
        kojihub.repo_init('test-tag', task_id)

        repodir = f'{self.tempdir}/repos/TAG/REPOID'
        expect = ['aarch64', 'groups', 'repo.json', 'x86_64']
        self.assertEqual(sorted(os.listdir(repodir)), expect)

        with open(f'{repodir}/repo.json', 'rt') as fo:
            info = json.load(fo)
        self.assertEqual(info['id'], 'REPOID')
        self.assertEqual(info['tag'], 'TAG')
        self.assertEqual(info['tag_id'], 137)
        self.assertEqual(info['task_id'], 100)
        self.assertEqual(info['event_id'], 'EVENTID')
        self.assertEqual(info['opts'], opts)
        self.assertEqual(info['custom_opts'], custom)

        # basic comps check
        with open(f'{repodir}/groups/comps.xml', 'rt') as fo:
            root = ElementTree.fromstring(fo.read())

        for arch in ['x86_64', 'aarch64']:
            # contents
            expect = ['blocklist', 'pkglist', 'rpmlist.jsonl', 'toplink']
            self.assertEqual(sorted(os.listdir(f'{repodir}/{arch}')), expect)

            # check toplink
            if not os.path.samefile(f'{repodir}/{arch}/toplink', self.tempdir):
                raise Exception('invalid toplink')

            # blocklist should be blank
            with open(f'{repodir}/{arch}/blocklist', 'rt') as fo:
                self.assertEqual(fo.read(), '')

            # check rpm contents
            # debuginfo included
            arch_rpms = [r for r in rpms if r['arch'] in ('noarch', arch)]
            with open(f'{repodir}/{arch}/rpmlist.jsonl', 'rt') as fo:
                repo_rpms = [json.loads(line) for line in fo]
                self.assertEqual(repo_rpms, arch_rpms)

            with open(f'{repodir}/{arch}/pkglist', 'rt') as fo:
                lines = fo.readlines()
                self.assertEqual(len(lines), len(arch_rpms))

    def test_taginfo_filtered_arches(self):
        # noarch and src should in the tag arch list should be ignored
        self.taginfo['arches'] = 'x86_64 noarch src'
        task_id = 100
        self.readTaggedRPMS.return_value = [], []
        kojihub.repo_init('test-tag', task_id)

        repodir = f'{self.tempdir}/repos/TAG/REPOID'
        expect = ['groups', 'repo.json', 'x86_64']
        self.assertEqual(sorted(os.listdir(repodir)), expect)

    def test_blocklist(self):
        task_id = 100
        self.readTaggedRPMS.return_value = [], []
        blocked = [{'id': n, 'package_name': f'package-{n}', 'blocked': True} for n in range(20)]
        notblocked = [{'id': n, 'package_name': f'package-{n}', 'blocked': False}
                      for n in range(20, 30)]
        packages = {p['id']: p for p in blocked + notblocked}
        self.readPackageList.return_value = packages
        kojihub.repo_init('test-tag', task_id)

        repodir = f'{self.tempdir}/repos/TAG/REPOID'

        for arch in ['x86_64', 'aarch64']:
            # contents
            expect = ['blocklist', 'pkglist', 'rpmlist.jsonl', 'toplink']
            self.assertEqual(sorted(os.listdir(f'{repodir}/{arch}')), expect)

            # check blocklist
            expected = [p['package_name'] for p in blocked]
            with open(f'{repodir}/{arch}/blocklist', 'rt') as fo:
                self.assertEqual(fo.read().splitlines(), expected)

    def test_repo_at_event(self):
        task_id = 100
        self.readTaggedRPMS.return_value = [], []
        kojihub.repo_init('test-tag', task_id, event=101010)

        self.singleValue.assert_not_called()

        repodir = f'{self.tempdir}/repos/TAG/REPOID'
        expect = ['aarch64', 'groups', 'repo.json', 'x86_64']
        self.assertEqual(sorted(os.listdir(repodir)), expect)

        with open(f'{repodir}/repo.json', 'rt') as fo:
            info = json.load(fo)
        self.assertEqual(info['id'], 'REPOID')
        self.assertEqual(info['tag'], 'TAG')
        self.assertEqual(info['tag_id'], 137)
        self.assertEqual(info['task_id'], 100)
        self.assertEqual(info['event_id'], 101010)
        self.assertEqual(info['opts'], self.default_opts)
        self.assertEqual(info['custom_opts'], {})


# the end
