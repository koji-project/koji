
import unittest
import mock
import os
import shutil
import tempfile

import koji
import kojihub
from koji.util import dslice_ex

IP = kojihub.InsertProcessor


class TestSignedRepoInit(unittest.TestCase):


    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert


    def setUp(self):
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                side_effect=self.getInsert).start()
        self.inserts = []
 
        self.get_tag = mock.patch('kojihub.get_tag').start()
        self.get_event = mock.patch('kojihub.get_event').start()
        self.nextval = mock.patch('kojihub.nextval').start()
        self.ensuredir = mock.patch('koji.ensuredir').start()
        self.copyfile = mock.patch('shutil.copyfile').start()

        self.get_tag.return_value = {'id': 42, 'name': 'tag'}
        self.get_event.return_value = 12345
        self.nextval.return_value = 99


    def tearDown(self):
        mock.patch.stopall()


    def test_simple_signed_repo_init(self):

        # simple case
        kojihub.signed_repo_init('tag', ['key'], {'arch': ['x86_64']})
        self.InsertProcessor.assert_called_once()

        ip = self.inserts[0]
        self.assertEquals(ip.table, 'repo')
        data = {'signed': True, 'create_event': 12345, 'tag_id': 42, 'id': 99,
                    'state': koji.REPO_STATES['INIT']}
        self.assertEquals(ip.data, data)
        self.assertEquals(ip.rawdata, {})

        # no comps option
        self.copyfile.assert_not_called()


    def test_signed_repo_init_with_comps(self):

        # simple case
        kojihub.signed_repo_init('tag', ['key'], {'arch': ['x86_64'],
                    'comps': 'COMPSFILE'})
        self.InsertProcessor.assert_called_once()

        ip = self.inserts[0]
        self.assertEquals(ip.table, 'repo')
        data = {'signed': True, 'create_event': 12345, 'tag_id': 42, 'id': 99,
                    'state': koji.REPO_STATES['INIT']}
        self.assertEquals(ip.data, data)
        self.assertEquals(ip.rawdata, {})

        # no comps option
        self.copyfile.assert_called_once()


class TestSignedRepo(unittest.TestCase):

    @mock.patch('kojihub.signed_repo_init')
    @mock.patch('kojihub.make_task')
    def test_SignedRepo(self, make_task, signed_repo_init):
        session = kojihub.context.session = mock.MagicMock()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        session.assertPerm = mock.MagicMock()
        signed_repo_init.return_value = ('repo_id', 'event_id')
        make_task.return_value = 'task_id'

        exports = kojihub.RootExports()
        ret = exports.signedRepo('tag', 'keys')
        session.assertPerm.assert_called_once_with('signed-repo')
        signed_repo_init.assert_called_once()
        make_task.assert_called_once()
        self.assertEquals(ret, make_task.return_value)


class TestSignedRepoMove(unittest.TestCase):

    def setUp(self):
        self.topdir = tempfile.mkdtemp()
        self.rinfo = {
            'create_event': 2915,
            'create_ts': 1487256924.72718,
            'creation_time': '2017-02-16 14:55:24.727181',
            'id': 47,
            'state': 1,
            'tag_id': 2,
            'tag_name': 'my-tag'}
        self.arch = 'x86_64'

        # set up a fake koji topdir
        # koji.pathinfo._topdir = self.topdir
        mock.patch('koji.pathinfo._topdir', new=self.topdir).start()
        repodir = koji.pathinfo.signedrepo(self.rinfo['id'], self.rinfo['tag_name'])
        archdir = "%s/%s" % (repodir, koji.canonArch(self.arch))
        os.makedirs(archdir)
        self.uploadpath = 'UNITTEST'
        workdir = koji.pathinfo.work()
        uploaddir = "%s/%s" % (workdir, self.uploadpath)
        os.makedirs(uploaddir)

        # place some test files
        self.files = ['foo.drpm', 'repomd.xml']
        self.expected = ['x86_64/drpms/foo.drpm', 'x86_64/repodata/repomd.xml']
        for fn in self.files:
            path = os.path.join(uploaddir, fn)
            koji.ensuredir(os.path.dirname(path))
            with open(path, 'w') as fo:
                fo.write('%s' % fn)

        # also a pkglist file
        self.files.append('pkglist')
        plist = os.path.join(uploaddir, 'pkglist')
        # crap this is terrible -- code needs fixing
        nvrs = ['aaa-1.0-2', 'bbb-3.0-5', 'ccc-8.0-13','ddd-21.0-34']
        self.fullpaths = {}  # XXX
        with open(plist, 'w') as f_pkglist:
            for nvr in nvrs:
                binfo = koji.parse_NVR(nvr)
                rpminfo = binfo.copy()
                rpminfo['arch'] = 'x86_64'
                builddir = koji.pathinfo.build(binfo)
                relpath = koji.pathinfo.rpm(rpminfo)
                path = os.path.join(builddir, relpath)
                koji.ensuredir(os.path.dirname(path))
                basename = os.path.basename(path)
                with open(path, 'w') as fo:
                    fo.write('%s' % basename)
                f_pkglist.write(path)
                f_pkglist.write('\n')
                self.expected.append('x86_64/%s/%s' % (basename[0], basename))
                self.fullpaths[basename] = path  # XXX

        # mocks
        self.repo_info = mock.patch('kojihub.repo_info').start()
        self.repo_info.return_value = self.rinfo.copy()


    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.topdir)


    def test_signedRepoMove(self):
        exports = kojihub.HostExports()
        exports.signedRepoMove(self.rinfo['id'], self.uploadpath,
                list(self.files), self.arch, self.fullpaths)
        # check result
        repodir = self.topdir + '/repos-signed/%(tag_name)s/%(id)s' % self.rinfo
        for relpath in self.expected:
            path = os.path.join(repodir, relpath)
            basename = os.path.basename(path)
            if not os.path.exists(path):
                raise Exception, "Missing file: %s" % path
            data = open(path).read()
            data.strip()
            self.assertEquals(data, basename)

