import unittest
import json
import mock
import os
import shutil
import tempfile

import koji
import kojihub
from koji.util import dslice_ex

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

        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                side_effect=self.getInsert).start()
        self.inserts = []
 
        self.get_tag = mock.patch('kojihub.get_tag').start()
        self.get_event = mock.patch('kojihub.get_event').start()
        self.nextval = mock.patch('kojihub.nextval').start()
        self.copyfile = mock.patch('shutil.copyfile').start()

        self.get_tag.return_value = {'id': 42, 'name': 'tag'}
        self.get_event.return_value = 12345
        self.nextval.return_value = 99


    def tearDown(self):
        mock.patch.stopall()


    def test_simple_dist_repo_init(self):

        # simple case
        kojihub.dist_repo_init('tag', ['key'], {'arch': ['x86_64']})
        self.InsertProcessor.assert_called_once()

        ip = self.inserts[0]
        self.assertEquals(ip.table, 'repo')
        data = {'dist': True, 'create_event': 12345, 'tag_id': 42, 'id': 99,
                    'state': koji.REPO_STATES['INIT']}
        self.assertEquals(ip.data, data)
        self.assertEquals(ip.rawdata, {})

        # no comps option
        self.copyfile.assert_not_called()


    def test_dist_repo_init_with_comps(self):

        # simple case
        kojihub.dist_repo_init('tag', ['key'], {'arch': ['x86_64'],
                    'comps': 'COMPSFILE'})
        self.InsertProcessor.assert_called_once()

        ip = self.inserts[0]
        self.assertEquals(ip.table, 'repo')
        data = {'dist': True, 'create_event': 12345, 'tag_id': 42, 'id': 99,
                    'state': koji.REPO_STATES['INIT']}
        self.assertEquals(ip.data, data)
        self.assertEquals(ip.rawdata, {})

        self.copyfile.assert_called_once()


class TestDistRepo(unittest.TestCase):

    @mock.patch('kojihub.assert_policy')
    @mock.patch('kojihub.dist_repo_init')
    @mock.patch('kojihub.make_task')
    def test_DistRepo(self, make_task, dist_repo_init, assert_policy):
        session = kojihub.context.session = mock.MagicMock()
        session.user_id = 123
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        session.hasPerm = mock.MagicMock()
        session.hasPerm.return_value = False
        dist_repo_init.return_value = ('repo_id', 'event_id')
        make_task.return_value = 'task_id'
        exports = kojihub.RootExports()
        exports.getBuildConfig = mock.MagicMock()
        exports.getBuildConfig.return_value = {'extra': {}}

        ret = exports.distRepo('tag', 'keys')

        session.hasPerm.has_calls(mock.call('dist_repo'), mock.call('admin'))
        assert_policy.assert_called_once_with('dist_repo', {'tag': 'tag'})
        dist_repo_init.assert_called_once()
        make_task.assert_called_once()
        self.assertEquals(ret, make_task.return_value)
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
            with open(path, 'w') as fo:
                fo.write('%s' % os.path.basename(fn))

        # generate pkglist file
        self.files.append('pkglist')
        plist = os.path.join(uploaddir, 'pkglist')
        nvrs = ['aaa-1.0-2', 'bbb-3.0-5', 'ccc-8.0-13','ddd-21.0-34']
        self.rpms = {}
        self.builds ={}
        self.key = '4c8da725'
        with open(plist, 'w') as f_pkglist:
            for nvr in nvrs:
                binfo = koji.parse_NVR(nvr)
                rpminfo = binfo.copy()
                rpminfo['arch'] = 'x86_64'
                builddir = koji.pathinfo.build(binfo)
                relpath = koji.pathinfo.signed(rpminfo, self.key)
                path = os.path.join(builddir, relpath)
                koji.ensuredir(os.path.dirname(path))
                basename = os.path.basename(path)
                with open(path, 'w') as fo:
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
        with open("%s/kojipkgs" % uploaddir, "w") as fp:
            json.dump(kojipkgs, fp, indent=4)
        self.files.append('kojipkgs')

        # write manifest
        with open("%s/repo_manifest" % uploaddir, "w") as fp:
            json.dump(self.files, fp, indent=4)

        # mocks
        self.repo_info = mock.patch('kojihub.repo_info').start()
        self.repo_info.return_value = self.rinfo.copy()
        self.get_rpm = mock.patch('kojihub.get_rpm').start()
        self.get_build = mock.patch('kojihub.get_build').start()
        self.get_rpm.side_effect = self.our_get_rpm
        self.get_build.side_effect = self.our_get_build


    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.topdir)


    def our_get_rpm(self, rpminfo, strict=False, multi=False):
        return self.rpms[rpminfo]


    def our_get_build(self, buildInfo, strict=False):
        return self.builds[buildInfo]


    def test_distRepoMove(self):
        session = kojihub.context.session = mock.MagicMock()
        session.user_id = 123
        exports = kojihub.HostExports()
        exports.distRepoMove(self.rinfo['id'], self.uploadpath, self.arch)
        # check result
        repodir = self.topdir + '/repos-dist/%(tag_name)s/%(id)s' % self.rinfo
        for relpath in self.expected:
            path = os.path.join(repodir, relpath)
            basename = os.path.basename(path)
            if not os.path.exists(path):
                raise Exception("Missing file: %s" % path)
            data = open(path).read()
            data.strip()
            self.assertEquals(data, basename)

