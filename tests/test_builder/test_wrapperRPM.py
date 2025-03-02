from __future__ import absolute_import
try:
    from unittest import mock
except ImportError:
    import mock
import os
import rpm
import shutil
import tempfile
import threading
import unittest
import koji
import koji.tasks
from .loadkojid import kojid
from six.moves import range
from functools import partial


mylock = threading.Lock()


class TestWrapperRPM(unittest.TestCase):

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
        method = 'wrapperRPM'
        self.spec_url = 'SPEC_URL'
        self.target = {'id': 123, 'name': 'TARGET', 'build_tag': 456}
        self.build = {'id': 12345, 'state': 1, 'name': '_name', 'version': '_version',
                      'release': '_release'}
        self.task = None
        self.opts = {}
        params = [self.spec_url, self.target, self.build, self.task, self.opts]
        self.handler = kojid.WrapperRPMTask(task_id, method, params, self.session,
                self.options, self.tempdir + '/work')

        self.handler.find_arch = mock.MagicMock()
        self.handler.chownTree = mock.MagicMock()
        self.handler.localPath = self.my_localPath

        # mock some more things
        self.wait = mock.MagicMock()
        self.handler.wait = self.wait
        self.session.getExternalRepoList.return_value = []
        self.SCM = mock.patch.object(kojid, 'SCM').start()
        self.SCM.return_value.assert_allowed = mock.MagicMock()
        self.SCM.return_value.checkout.side_effect = self.my_checkout
        self.BuildRoot = mock.patch.object(kojid, 'BuildRoot').start()
        self.BuildRoot().resultdir.return_value = self.tempdir + '/result'
        mock.patch('pwd.getpwnam').start()
        mock.patch('grp.getgrnam').start()

        # default to a maven build
        self.session.getMavenBuild.return_value = {'build_id': 12345, 'artifact_id': 'ARTIFACT'}
        self.session.getWinBuild.return_value = None
        self.session.getImageBuild.return_value = None

        self.session.listArchives.return_value = [{'id': 999, 'filename': 'test.pom',
                                                   'group_id': 'GROUP', 'artifact_id': 'ARTIFACT',
                                                   'version': 'VERSION', 'name': 'NAME'}]
        # This handler relies on chdir
        mylock.acquire()
        self.savecwd = os.getcwd()

    def tearDown(self):
        # clean up the chdir
        os.chdir(self.savecwd)
        mylock.release()
        mock.patch.stopall()
        shutil.rmtree(self.tempdir)

    def my_checkout(self, *a, **kw):
        return self.my_checkout2(['foo.spec.tmpl'], *a, **kw)

    def my_checkout2(self, relpaths, *a, **kw):
        scmdir = self.tempdir + '/checkout'
        koji.ensuredir(scmdir)
        for relpath in relpaths:
            fn = koji.util.joinpath(scmdir, relpath)
            with open(fn, 'wt') as fp:
                fp.write(f'Hello World\n{relpath}\n')
        return scmdir

    def my_localPath(self, relpath):
        path = koji.util.joinpath(self.tempdir, relpath)
        koji.ensuredir(os.path.dirname(path))
        with open(path, 'wt') as fp:
            fp.write('Hola Mundo\n')
        return path

    def write_srpm(self):
        fn = self.tempdir + '/result/foo.src.rpm'
        koji.ensuredir(os.path.dirname(fn))
        with open(fn, 'wt') as fp:
            fp.write('Bonjour le monde\n')

    def my_build(self, *a, **kw):
        self.write_srpm()
        fn = self.tempdir + '/result/foo.noarch.rpm'
        koji.ensuredir(os.path.dirname(fn))
        with open(fn, 'wt') as fp:
            fp.write('Ahoj světe\n')

    def test_basic(self):
        # self.session.getTag.return_value = {'id': 'TAGID', 'name': 'TAG'}
        self.write_srpm()
        # rewrite the srpm when build is called
        self.BuildRoot().build.side_effect = self.my_build

        # this handler relies on os.chdir
        result = self.handler.run()

        self.assertEqual(result['srpm'], 'foo.src.rpm')
        self.assertEqual(result['rpms'], ['foo.noarch.rpm'])


    def test_basic_jinja(self):
        # self.session.getTag.return_value = {'id': 'TAGID', 'name': 'TAG'}
        self.write_srpm()
        # rewrite the srpm when build is called
        self.BuildRoot().build.side_effect = self.my_build
        # use a jinja template
        self.SCM.return_value.checkout.side_effect = partial(self.my_checkout2, ['foo.spec.j2'])

        # this handler relies on os.chdir
        self.opts['jinja'] = True
        result = self.handler.run()

        self.assertEqual(result['srpm'], 'foo.src.rpm')
        self.assertEqual(result['rpms'], ['foo.noarch.rpm'])

    def test_jinja_requires_opt(self):
        # self.session.getTag.return_value = {'id': 'TAGID', 'name': 'TAG'}
        self.write_srpm()
        # rewrite the srpm when build is called
        self.BuildRoot().build.side_effect = self.my_build
        # use a jinja template
        self.SCM.return_value.checkout.side_effect = partial(self.my_checkout2, ['foo.spec.j2'])

        # this handler relies on os.chdir
        with self.assertRaises(koji.BuildError) as ex:
            result = self.handler.run()

        self.assertIn('no spec file template found', str(ex.exception))


# the end
