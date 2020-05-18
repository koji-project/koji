import copy
import json
import mock
import os
import os.path
import shutil
import tempfile
import unittest

import koji
import koji.util
import kojihub


orig_import_archive_internal = kojihub.import_archive_internal


class TestCompleteMavenBuild(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.pathinfo = koji.PathInfo(self.tempdir)
        mock.patch('koji.pathinfo', new=self.pathinfo).start()
        self.hostcalls = kojihub.HostExports()
        self.context = mock.patch('kojihub.context').start()
        self.context.opts = {'EnableMaven': True}
        mock.patch('kojihub.Host').start()
        self.Task = mock.patch('kojihub.Task').start()
        self.Task.return_value.assertHost = mock.MagicMock()
        self.get_build = mock.patch('kojihub.get_build').start()
        self.get_maven_build = mock.patch('kojihub.get_maven_build').start()
        self.get_archive_type = mock.patch('kojihub.get_archive_type').start()
        mock.patch('kojihub.lookup_name', new=self.my_lookup_name).start()
        mock.patch.object(kojihub.BuildRoot, 'load', new=self.my_buildroot_load).start()
        mock.patch('kojihub.import_archive_internal',
                    new=self.my_import_archive_internal).start()
        mock.patch('kojihub._dml').start()
        mock.patch('kojihub._fetchSingle').start()
        mock.patch('kojihub.build_notification').start()
        mock.patch('kojihub.assert_policy').start()
        mock.patch('kojihub.check_volume_policy',
                return_value={'id':0, 'name': 'DEFAULT'}).start()
        self.set_up_callbacks()

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.tempdir)

    def set_up_files(self, name):
        datadir = os.path.join(os.path.dirname(__file__), 'data/maven', name)
        # load maven result data for our test build
        data = json.load(open(datadir + '/data.json'))
        data['task_id'] = 9999
        taskdir = koji.pathinfo.task(data['task_id'])
        for subdir in data['files']:
            path = os.path.join(taskdir, subdir)
            os.makedirs(path)
            for fn in data['files'][subdir]:
                src = os.path.join(datadir, subdir, fn)
                dst = os.path.join(path, fn)
                shutil.copy(src, dst)
        for fn in data['logs']:
            src = os.path.join(datadir, fn)
            dst = os.path.join(taskdir, fn)
            shutil.copy(src, dst)
        self.maven_data = data
        files = open(datadir + '/files').readlines()
        files = [l.strip() for l in files]
        self.expected_files = files

    def my_lookup_name(self, table, info, **kw):
        if table == 'btype':
            return {'name': 'maven', 'id': 1234}
        else:
            raise Exception("Cannot fake call")

    @staticmethod
    def my_buildroot_load(br, id):
        # br is the BuildRoot instance
        br.id = id
        br.is_standard = True
        br.data = {
                'br_type': koji.BR_TYPES['STANDARD'],
                'id': id,
                }

    def my_import_archive_internal(self, *a, **kw):
        # this is kind of odd, but we need this to fake the archiveinfo
        share = {}
        def my_ip(table, *a, **kw):
            if table == 'archiveinfo':
                share['archiveinfo'] = kw['data']
                # TODO: need to add id
            return mock.MagicMock()
        def my_ga(archive_id, **kw):
            return share['archiveinfo']
        with mock.patch('kojihub.InsertProcessor', new=my_ip):
            with mock.patch('kojihub.get_archive', new=my_ga):
                orig_import_archive_internal(*a, **kw)

    def set_up_callbacks(self):
        new_callbacks = copy.deepcopy(koji.plugin.callbacks)
        mock.patch('koji.plugin.callbacks', new=new_callbacks).start()
        self.callbacks = []
        for cbtype in koji.plugin.callbacks.keys():
            koji.plugin.register_callback(cbtype, self.callback)

    def callback(self, cbtype, *args, **kwargs):
        self.callbacks.append([cbtype, args, kwargs])

    def test_complete_maven_build(self):
        self.set_up_files('import_1')
        buildinfo = koji.maven_info_to_nvr(self.maven_data['maven_info'])
        buildinfo['id'] = 137
        buildinfo['task_id'] = 'TASK_ID'
        buildinfo['release'] = '1'
        buildinfo['source'] = None
        buildinfo['state'] = koji.BUILD_STATES['BUILDING']
        buildinfo['volume_id'] = 0
        buildinfo['volume_name'] = 'DEFAULT'
        buildinfo['extra'] = {}
        maven_info = self.maven_data['maven_info'].copy()
        maven_info['build_id'] = buildinfo['id']
        self.get_build.return_value = buildinfo
        self.get_maven_build.return_value = maven_info
        self.hostcalls.completeMavenBuild('TASK_ID', 'BUILD_ID', self.maven_data, None)
        # make sure we wrote the files we expect
        files = []
        for dirpath, dirnames, filenames in os.walk(self.tempdir + '/packages'):
            relpath = os.path.relpath(dirpath, self.tempdir)
            files.extend([os.path.join(relpath, fn) for fn in filenames])
        self.assertEqual(set(files), set(self.expected_files))
        # check callbacks
        cbtypes = [c[0] for c in self.callbacks]
        cb_expect = [
            'preImport',    # archive 1...
            'postImport',
            'preImport',    # archive 2...
            'postImport',
            'preImport',    # archive 3...
            'postImport',
            'preBuildStateChange',  # building -> completed
            'postBuildStateChange',
            ]
        self.assertEqual(cbtypes, cb_expect)

        cb_idx = {}

        cb_idx = {}
        for c in self.callbacks:
            # no callbacks should use *args
            self.assertEqual(c[1], ())
            cbtype = c[0]
            if 'type' in c[2]:
                key = "%s:%s" % (cbtype, c[2]['type'])
            else:
                key = cbtype
            cb_idx.setdefault(key, [])
            cb_idx[key].append(c[2])
        key_expect = ['postBuildStateChange', 'preBuildStateChange', 'preImport:archive', 'postImport:archive']
        self.assertEqual(set(cb_idx.keys()), set(key_expect))
        # in this case, pre and post data is similar
        for key in ['preImport:archive', 'postImport:archive']:
            callbacks = cb_idx[key]
            self.assertEqual(len(callbacks), 3)
            for cbargs in callbacks:
                keys = set(cbargs.keys())
                k_expect = set(['filepath', 'build_type', 'build', 'fileinfo', 'type', 'archive'])
                self.assertEqual(keys, k_expect)
                self.assertEqual(cbargs['type'], 'archive')
                self.assertEqual(cbargs['build'], buildinfo)
