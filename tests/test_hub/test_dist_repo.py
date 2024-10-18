import unittest
from unittest import mock
import os
import shutil
import tempfile

import koji
import kojihub

IP = kojihub.InsertProcessor


class TestDistRepoInit(unittest.TestCase):

    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.pathinfo = koji.PathInfo(self.tempdir)
        mock.patch('koji.pathinfo', new=self.pathinfo).start()

        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []

        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.get_event = mock.patch('kojihub.kojihub.get_event').start()
        self.nextval = mock.patch('kojihub.kojihub.nextval').start()
        self.copyfile = mock.patch('shutil.copyfile').start()
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name').start()

        self.get_tag.return_value = {'id': 42, 'name': 'tag'}
        self.get_event.return_value = 12345
        self.nextval.return_value = 99

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.tempdir)

    def test_simple_dist_repo_init(self):

        # simple case
        kojihub.dist_repo_init('tag', ['key'], {'arch': ['x86_64']})
        self.InsertProcessor.assert_called_once()

        ip = self.inserts[0]
        self.assertEqual(ip.table, 'repo')
        data = {'dist': True, 'create_event': 12345, 'tag_id': 42, 'id': 99,
                'state': koji.REPO_STATES['INIT']}
        self.assertEqual(ip.data, data)
        self.assertEqual(ip.rawdata, {})

        # no comps option
        self.copyfile.assert_not_called()

    def test_dist_repo_init_with_comps(self):

        # simple case
        kojihub.dist_repo_init('tag', ['key'], {'arch': ['x86_64'], 'comps': 'COMPSFILE'})
        self.InsertProcessor.assert_called_once()

        ip = self.inserts[0]
        self.assertEqual(ip.table, 'repo')
        data = {'dist': True, 'create_event': 12345, 'tag_id': 42, 'id': 99,
                'state': koji.REPO_STATES['INIT']}
        self.assertEqual(ip.data, data)
        self.assertEqual(ip.rawdata, {})

        self.copyfile.assert_called_once()

    def test_simple_dist_repo_init_wrong_type_keys(self):
        keys = 'key1 key2'
        with self.assertRaises(koji.ParameterError) as cm:
            kojihub.dist_repo_init('tag', keys, {'arch': ['x86_64']})
        self.assertEqual(f"Invalid type for value '{keys}': {type(keys)}, "
                         f"expected type <class 'list'>", str(cm.exception))
        self.InsertProcessor.assert_not_called()

    def test_simple_dist_repo_init_wrong_type_task_opts(self):
        task_opts = 'opts'
        with self.assertRaises(koji.ParameterError) as cm:
            kojihub.dist_repo_init('tag', ['key'], task_opts)
        self.assertEqual(f"Invalid type for value '{task_opts}': {type(task_opts)}, "
                         f"expected type <class 'dict'>",
                         str(cm.exception))
        self.InsertProcessor.assert_not_called()

    def test_simple_dist_repo_init_wrong_type_event(self):
        event = 'test-event'
        with self.assertRaises(koji.ParameterError) as cm:
            kojihub.dist_repo_init('tag', ['key'], {'arch': ['x86_64'], 'event': event})
        self.assertEqual(f"Invalid type for value '{event}': {type(event)}, "
                         f"expected type <class 'int'>", str(cm.exception))
        self.InsertProcessor.assert_not_called()

    def test_simple_dist_repo_init_wrong_type_volume(self):
        self.lookup_name.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub.dist_repo_init('tag', ['key'], {'arch': ['x86_64'], 'volume': 'test-volume'})
        self.InsertProcessor.assert_not_called()


class TestDistRepo(unittest.TestCase):

    def setUp(self):
        self.assert_policy = mock.patch('kojihub.kojihub.assert_policy').start()
        self.dist_repo_init = mock.patch('kojihub.kojihub.dist_repo_init').start()
        self.make_task = mock.patch('kojihub.kojihub.make_task').start()
        self.context = mock.patch('kojihub.kojihub.context').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_DistRepo(self):
        session = self.context.session
        session.user_id = 123
        session.hasPerm.return_value = False
        self.dist_repo_init.return_value = ('repo_id', 'event_id')
        self.make_task.return_value = 'task_id'
        exports = kojihub.RootExports()
        exports.getBuildConfig = mock.MagicMock()
        exports.getBuildConfig.return_value = {'extra': {}}

        ret = exports.distRepo('tag', 'keys')

        session.hasPerm.assert_has_calls([mock.call('dist-repo'), mock.call('admin')])
        self.assert_policy.assert_called_once_with('dist_repo', {'tag': 'tag'})
        self.dist_repo_init.assert_called_once()
        self.make_task.assert_called_once()
        self.assertEqual(ret, self.make_task.return_value)
        exports.getBuildConfig.assert_called_once_with('tag')


class TestDistRepoMove(unittest.TestCase):

    def setUp(self):
        self.topdir = tempfile.mkdtemp()
        self.rinfo = {
            'create_event': 2915,
            'create_ts': 1487256924.72718,
            'creation_time': '2017-02-16 14:55:24.727181',
            'id': 47,
            'state': 0,  # INIT
            'tag_id': 2,
            'tag_name': 'my-tag'}
        self.arch = 'x86_64'

        # set up a fake koji topdir
        # koji.pathinfo._topdir = self.topdir
        mock.patch('koji.pathinfo._topdir', new=self.topdir).start()
        repodir = koji.pathinfo.distrepo(self.rinfo['id'], self.rinfo['tag_name'])
        archdir = "%s/%s" % (repodir, koji.canonArch(self.arch))
        os.makedirs(archdir)
        self.uploadpath = 'UNITTEST'
        workdir = koji.pathinfo.work()
        uploaddir = "%s/%s" % (workdir, self.uploadpath)
        os.makedirs(uploaddir)

        # place some test files
        self.files = ['drpms/foo.drpm', 'repodata/repomd.xml']
        self.expected = ['x86_64/drpms/foo.drpm', 'x86_64/repodata/repomd.xml']
        for fn in self.files:
            path = os.path.join(uploaddir, fn)
            koji.ensuredir(os.path.dirname(path))
            with open(path, 'wt', encoding='utf-8') as fo:
                fo.write('%s' % os.path.basename(fn))

        # generate pkglist file
        self.files.append('pkglist')
        plist = os.path.join(uploaddir, 'pkglist')
        nvrs = ['aaa-1.0-2', 'bbb-3.0-5', 'ccc-8.0-13', 'ddd-21.0-34']
        self.rpms = {}
        self.builds = {}
        self.key = '4c8da725'
        with open(plist, 'wt', encoding='utf-8') as f_pkglist:
            for nvr in nvrs:
                binfo = koji.parse_NVR(nvr)
                rpminfo = binfo.copy()
                rpminfo['arch'] = 'x86_64'
                builddir = koji.pathinfo.build(binfo)
                relpath = koji.pathinfo.signed(rpminfo, self.key)
                path = os.path.join(builddir, relpath)
                koji.ensuredir(os.path.dirname(path))
                basename = os.path.basename(path)
                with open(path, 'wt', encoding='utf-8') as fo:
                    fo.write('%s' % basename)
                f_pkglist.write(path)
                f_pkglist.write('\n')
                self.expected.append('x86_64/Packages/%s/%s' % (basename[0], basename))
                build_id = len(self.builds) + 10000
                rpm_id = len(self.rpms) + 20000
                binfo['id'] = build_id
                rpminfo['build_id'] = build_id
                rpminfo['id'] = rpm_id
                rpminfo['sigkey'] = self.key
                rpminfo['size'] = 1024
                rpminfo['payloadhash'] = 'helloworld'
                self.builds[build_id] = binfo
                self.rpms[rpm_id] = rpminfo

        # write kojipkgs
        kojipkgs = {}
        for rpminfo in self.rpms.values():
            bnp = '%(name)s-%(version)s-%(release)s.%(arch)s.rpm' % rpminfo
            kojipkgs[bnp] = rpminfo
        koji.dump_json("%s/kojipkgs" % uploaddir, kojipkgs)
        self.files.append('kojipkgs')

        # write manifest
        koji.dump_json("%s/repo_manifest" % uploaddir, self.files)

        # mocks
        self.repo_info = mock.patch('kojihub.kojihub.repo_info').start()
        self.repo_info.return_value = self.rinfo.copy()
        self.get_rpm = mock.patch('kojihub.kojihub.get_rpm').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.get_rpm.side_effect = self.our_get_rpm
        self.get_build.side_effect = self.our_get_build
        self.context = mock.patch('kojihub.kojihub.context').start()

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.topdir)

    def our_get_rpm(self, rpminfo, strict=False, multi=False):
        return self.rpms[rpminfo]

    def our_get_build(self, buildInfo, strict=False):
        return self.builds[buildInfo]

    def test_distRepoMove(self):
        session = self.context.session
        session.user_id = 123
        exports = kojihub.HostExports()
        exports.distRepoMove(self.rinfo['id'], self.uploadpath, self.arch)
        # check result
        repodir = self.topdir + '/repos-dist/%(tag_name)s/%(id)s' % self.rinfo
        for relpath in self.expected:
            path = os.path.join(repodir, relpath)
            basename = os.path.basename(path)
            if not os.path.exists(path):
                raise Exception(f"Missing file: {path}")
            data = open(path, 'rt', encoding='utf-8').read()
            data.strip()
            self.assertEqual(data, basename)
