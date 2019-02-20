from __future__ import absolute_import
import logging
import mock
import shutil
import six
import tempfile
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji
import koji.daemon

from koji.daemon import SCM


class TestSCM(unittest.TestCase):

    def test_urlcheck(self):
        good = [
            "git://server/foo.git#bab0c73900241ef5c465d7e873e9d8b34c948e67",
            "git+ssh://server2/other/path#bab0c73900241ef5c465d7e873e9d8b34c948e67",
            "svn://server/path/to/code#bab0c73900241ef5c465d7e873e9d8b34c948e67",
            "svn+ssh://server/some/path#bab0c73900241ef5c465d7e873e9d8b34c948e67",
            "cvs://server/some/path#bab0c73900241ef5c465d7e873e9d8b34c948e67",
            "cvs+ssh://server/some/path#bab0c73900241ef5c465d7e873e9d8b34c948e67",
            ]
        bad = [
            "http://localhost/foo.html",
            "foo-1.1-1.src.rpm",
            "https://server/foo-1.1-1.src.rpm",
            "git:foobar",
            "https:foo/bar",
            "https://",
            ]
        for url in good:
            self.assertTrue(SCM.is_scm_url(url))
        for url in bad:
            self.assertFalse(SCM.is_scm_url(url))

    @mock.patch('logging.getLogger')
    def test_init(self, getLogger):
        bad = [
            "git://user@@server/foo.git#bab0c73900241ef5c465d7e873e9d8b34c948e67",
            "git://user:pass@server/foo.git#bab0c73900241ef5c465d7e873e9d8b34c948e67",
            "git://server/foo.git;params=not_allowed",
            "git://server#asdasd",  # no path
            "git://server/foo.git",  # no fragment
            "http://localhost/foo.html",
            "git://@localhost/foo/?a=bar/",
            "http://localhost/foo.html?a=foo/",
            "foo-1.1-1.src.rpm",
            "git://",
            "https://server/foo-1.1-1.src.rpm",
            ]
        for url in bad:
            with self.assertRaises(koji.GenericError):
                scm = SCM(url)

        url = "git://user@server/foo.git#bab0c73900241ef5c465d7e873e9d8b34c948e67"
        scm = SCM(url)
        self.assertEqual(scm.scheme, 'git://')
        self.assertEqual(scm.user, 'user')
        self.assertEqual(scm.host, 'server')
        self.assertEqual(scm.repository, '/foo.git')
        self.assertEqual(scm.module, '')
        self.assertEqual(scm.revision, 'bab0c73900241ef5c465d7e873e9d8b34c948e67')
        self.assertEqual(scm.use_common, True)
        self.assertEqual(scm.source_cmd, ['make', 'sources'])
        self.assertEqual(scm.scmtype, 'GIT')

    @mock.patch('logging.getLogger')
    def test_allowed(self, getLogger):
        config = '''
            goodserver:*:no
            !badserver:*
            !maybeserver:/badpath/*
            maybeserver:*:no
            '''
        good = [
            "git://goodserver/path1#1234",
            "git+ssh://maybeserver/path1#1234",
            ]
        bad = [
            "cvs://badserver/projects/42#ref",
            "svn://badserver/projects/42#ref",
            "git://maybeserver/badpath/project#1234",
            "git://maybeserver//badpath/project#1234",
            "git://maybeserver////badpath/project#1234",
            "git://maybeserver/./badpath/project#1234",
            "git://maybeserver//.//badpath/project#1234",
            "git://maybeserver/goodpath/../badpath/project#1234",
            "git://maybeserver/goodpath/..//badpath/project#1234",
            "git://maybeserver/..//badpath/project#1234",
            ]
        for url in good:
            scm = SCM(url)
            scm.assert_allowed(config)
        for url in bad:
            scm = SCM(url)
            try:
                scm.assert_allowed(config)
            except koji.BuildError:
                pass
            else:
                raise AssertionError("allowed bad url: %s" % url)

    @mock.patch('logging.getLogger')
    def test_badrule(self, getLogger):
        config = '''
            bogus-entry-should-be-ignored
            goodserver:*:no
            !badserver:*
            '''
        url = "git://goodserver/path1#1234"
        scm = SCM(url)
        scm.assert_allowed(config)

    @mock.patch('logging.getLogger')
    def test_opts(self, getLogger):
        config = '''
            default:*
            nocommon:*:no
            srccmd:*:no:fedpkg,sources
            nosrc:*:no:
            mixed:/foo/*:no
            mixed:/bar/*:yes
            mixed:/baz/*:no:fedpkg,sources
            '''

        url = "git://default/koji.git#1234"
        scm = SCM(url)
        scm.assert_allowed(config)
        self.assertEqual(scm.use_common, True)
        self.assertEqual(scm.source_cmd, ['make', 'sources'])

        url = "git://nocommon/koji.git#1234"
        scm = SCM(url)
        scm.assert_allowed(config)
        self.assertEqual(scm.use_common, False)
        self.assertEqual(scm.source_cmd, ['make', 'sources'])

        url = "git://srccmd/koji.git#1234"
        scm = SCM(url)
        scm.assert_allowed(config)
        self.assertEqual(scm.use_common, False)
        self.assertEqual(scm.source_cmd, ['fedpkg', 'sources'])

        url = "git://nosrc/koji.git#1234"
        scm = SCM(url)
        scm.assert_allowed(config)
        self.assertEqual(scm.use_common, False)
        self.assertEqual(scm.source_cmd, None)

        url = "git://mixed/foo/koji.git#1234"
        scm = SCM(url)
        scm.assert_allowed(config)
        self.assertEqual(scm.use_common, False)
        self.assertEqual(scm.source_cmd, ['make', 'sources'])

        url = "git://mixed/bar/koji.git#1234"
        scm = SCM(url)
        scm.assert_allowed(config)
        self.assertEqual(scm.use_common, True)
        self.assertEqual(scm.source_cmd, ['make', 'sources'])

        url = "git://mixed/baz/koji.git#1234"
        scm = SCM(url)
        scm.assert_allowed(config)
        self.assertEqual(scm.use_common, False)
        self.assertEqual(scm.source_cmd, ['fedpkg', 'sources'])

        url = "git://mixed/koji.git#1234"
        scm = SCM(url)
        with self.assertRaises(koji.BuildError):
            scm.assert_allowed(config)

        url = "git://mixed/foo/koji.git#1234"
        scm = SCM(url)
        scm.assert_allowed(config)
        self.assertEqual(scm.use_common, False)
        self.assertEqual(scm.source_cmd, ['make', 'sources'])

        url = "git://mixed/bar/koji.git#1234"
        scm = SCM(url)
        scm.assert_allowed(config)
        self.assertEqual(scm.use_common, True)
        self.assertEqual(scm.source_cmd, ['make', 'sources'])

        url = "git://mixed/baz/koji.git#1234"
        scm = SCM(url)
        scm.assert_allowed(config)
        self.assertEqual(scm.use_common, False)
        self.assertEqual(scm.source_cmd, ['fedpkg', 'sources'])

        url = "git://mixed/koji.git#1234"
        scm = SCM(url)
        with self.assertRaises(koji.BuildError):
            scm.assert_allowed(config)


class TestSCMCheckouts(unittest.TestCase):

    def setUp(self):
        self.symlink = mock.patch('os.symlink').start()
        self.getLogger = mock.patch('logging.getLogger').start()
        self.log_output = mock.patch('koji.daemon.log_output').start()
        self.log_output.return_value = None
        self.tempdir = tempfile.mkdtemp()
        self.session = mock.MagicMock()
        self.uploadpath = mock.MagicMock()
        self.logfile = '/dev/null'
        self.config = '''
            default:*
            nocommon:*:no
            srccmd:*:no:fedpkg,sources
            nosrc:*:no:
            '''

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.tempdir)

    def test_checkout_git_nocommon(self):

        url = "git://nocommon/koji.git#asdasd"
        scm = SCM(url)
        scm.assert_allowed(self.config)
        scm.checkout(self.tempdir, session=self.session,
                uploadpath=self.uploadpath, logfile=self.logfile)
        self.assertEqual(scm.use_common, False)
        self.symlink.assert_not_called()
        # expected commands
        cmd = ['git', 'clone', '-n', 'git://nocommon/koji.git',
                self.tempdir + '/koji']
        call1 = mock.call(self.session, cmd[0], cmd, self.logfile,
                        self.uploadpath, cwd=self.tempdir, logerror=1,
                        append=False, env=None)
        cmd = ['git', 'reset', '--hard', 'asdasd']
        call2 = mock.call(self.session, cmd[0], cmd, self.logfile,
                        self.uploadpath, cwd=self.tempdir + '/koji',
                        logerror=1, append=True, env=None)
        self.log_output.assert_has_calls([call1, call2])

    def test_checkout_gitssh_nocommon(self):

        url = "git+ssh://user@nocommon/koji.git#asdasd"
        scm = SCM(url)
        scm.assert_allowed(self.config)
        scm.checkout(self.tempdir, session=self.session,
                uploadpath=self.uploadpath, logfile=self.logfile)
        self.assertEqual(scm.use_common, False)
        self.symlink.assert_not_called()
        # expected commands
        cmd = ['git', 'clone', '-n', 'git+ssh://user@nocommon/koji.git',
                self.tempdir + '/koji']
        call1 = mock.call(self.session, cmd[0], cmd, self.logfile,
                        self.uploadpath, cwd=self.tempdir, logerror=1,
                        append=False, env=None)
        cmd = ['git', 'reset', '--hard', 'asdasd']
        call2 = mock.call(self.session, cmd[0], cmd, self.logfile,
                        self.uploadpath, cwd=self.tempdir + '/koji',
                        logerror=1, append=True, env=None)
        self.log_output.assert_has_calls([call1, call2])

    def test_checkout_git_common(self):

        url = "git://default/koji.git#asdasd"
        scm = SCM(url)
        scm.assert_allowed(self.config)
        scm.checkout(self.tempdir, session=self.session,
                uploadpath=self.uploadpath, logfile=self.logfile)
        self.assertEqual(scm.use_common, True)
        self.symlink.assert_called_once()
        # expected commands
        cmd = ['git', 'clone', '-n', 'git://default/koji.git',
                self.tempdir + '/koji']
        call1 = mock.call(self.session, cmd[0], cmd, self.logfile,
                        self.uploadpath, cwd=self.tempdir, logerror=1,
                        append=False, env=None)
        cmd = ['git', 'reset', '--hard', 'asdasd']
        call2 = mock.call(self.session, cmd[0], cmd, self.logfile,
                        self.uploadpath, cwd=self.tempdir + '/koji',
                        logerror=1, append=True, env=None)
        cmd = ['git', 'clone', 'git://default/common.git', 'common']
        call3 = mock.call(self.session, cmd[0], cmd, self.logfile,
                        self.uploadpath, cwd=self.tempdir,
                        logerror=1, append=True, env=None)
        self.log_output.assert_has_calls([call1, call2, call3])

    def test_checkout_error_in_command(self):

        url = "git://nocommon/koji.git#asdasd"
        scm = SCM(url)
        scm.assert_allowed(self.config)
        self.log_output.return_value = 1
        with self.assertRaises(koji.BuildError):
            scm.checkout(self.tempdir, session=self.session,
                    uploadpath=self.uploadpath, logfile=self.logfile)
        self.assertEqual(scm.use_common, False)
        self.symlink.assert_not_called()
        # expected commands
        cmd = ['git', 'clone', '-n', 'git://nocommon/koji.git',
                self.tempdir + '/koji']
        call1 = mock.call(self.session, cmd[0], cmd, self.logfile,
                        self.uploadpath, cwd=self.tempdir, logerror=1,
                        append=False, env=None)
        # should have errored after first command
        self.log_output.assert_has_calls([call1])

    def test_checkout_cvs_common(self):

        url = "cvs://default/cvsisdead?rpms/foo/EL3#sometag"
        scm = SCM(url)
        scm.assert_allowed(self.config)
        scm.checkout(self.tempdir, session=self.session,
                uploadpath=self.uploadpath, logfile=self.logfile)
        self.assertEqual(scm.use_common, True)
        self.symlink.assert_called_once()
        # expected commands
        cmd = ['cvs', '-d', ':pserver:anonymous@default:/cvsisdead', 'checkout',
                '-r', 'sometag', 'rpms/foo/EL3']
        call1 = mock.call(self.session, cmd[0], cmd, self.logfile,
                        self.uploadpath, cwd=self.tempdir, logerror=1,
                        append=False, env=None)
        cmd = ['cvs', '-d', ':pserver:anonymous@default:/cvsisdead', 'checkout',
                'common']
        call2 = mock.call(self.session, cmd[0], cmd, self.logfile,
                        self.uploadpath, cwd=self.tempdir, logerror=1,
                        append=True, env=None)
        self.log_output.assert_has_calls([call1, call2])

    def test_checkout_cvs_ssh(self):

        url = "cvs+ssh://user@nocommon/cvsisdead?rpms/foo/EL3#sometag"
        scm = SCM(url)
        scm.assert_allowed(self.config)
        scm.checkout(self.tempdir, session=self.session,
                uploadpath=self.uploadpath, logfile=self.logfile)
        self.assertEqual(scm.use_common, False)
        self.symlink.assert_not_called()
        # expected commands
        cmd = ['cvs', '-d', ':ext:user@nocommon:/cvsisdead', 'checkout', '-r',
                'sometag', 'rpms/foo/EL3']
        call1 = mock.call(self.session, cmd[0], cmd, self.logfile,
                        self.uploadpath, cwd=self.tempdir, logerror=1,
                        append=False, env={'CVS_RSH': 'ssh'})
        self.log_output.assert_has_calls([call1])

    def test_checkout_svn(self):

        url = "svn://nocommon/dist?rpms/foo/EL3#revision"
        scm = SCM(url)
        scm.assert_allowed(self.config)
        scm.checkout(self.tempdir, session=self.session,
                uploadpath=self.uploadpath, logfile=self.logfile)
        self.assertEqual(scm.use_common, False)
        self.symlink.assert_not_called()
        # expected commands
        cmd = ['svn', 'checkout', '-r', 'revision',
                'svn://nocommon/dist/rpms/foo/EL3', 'rpms/foo/EL3']
        call1 = mock.call(self.session, cmd[0], cmd, self.logfile,
                        self.uploadpath, cwd=self.tempdir, logerror=1,
                        append=False, env=None)
        self.log_output.assert_has_calls([call1])

    def test_checkout_svn_ssh(self):

        url = "svn+ssh://user@nocommon/dist?rpms/foo/EL3#revision"
        scm = SCM(url)
        scm.assert_allowed(self.config)
        scm.checkout(self.tempdir, session=self.session,
                uploadpath=self.uploadpath, logfile=self.logfile)
        self.assertEqual(scm.use_common, False)
        self.symlink.assert_not_called()
        # expected commands
        cmd = ['svn', 'checkout', '-r', 'revision',
                'svn+ssh://user@nocommon/dist/rpms/foo/EL3', 'rpms/foo/EL3']
        call1 = mock.call(self.session, cmd[0], cmd, self.logfile,
                        self.uploadpath, cwd=self.tempdir, logerror=1,
                        append=False, env=None)
        self.log_output.assert_has_calls([call1])

    @mock.patch('subprocess.Popen')
    def test_get_source_git(self, popen):
        popen.return_value.wait.return_value = 0
        popen.return_value.communicate = mock.MagicMock()
        popen.return_value.communicate.return_value = (six.b('hash '), six.b('any'))

        url = "git://default/koji.git#asdasd"
        scm = SCM(url)
        scm.assert_allowed(self.config)
        scm.checkout(self.tempdir, session=self.session,
                uploadpath=self.uploadpath, logfile=self.logfile)

        source = scm.get_source()
        self.assertEqual(source, {'url': url,
                                  'source': 'git://default/koji.git#hash'})

        popen.return_value.wait.return_value = 1
        with self.assertRaises(koji.GenericError) as cm:
            source = scm.get_source()
        self.assertEqual(cm.exception.args[0],
                         'Error getting commit hash for git')

    @mock.patch('subprocess.Popen')
    def test_get_source_other(self, popen):
        popen.return_value.wait.return_value = 0
        popen.return_value.communicate = mock.MagicMock()
        popen.return_value.communicate.return_value = ('hash ', 'any')

        url = "svn+ssh://user@nocommon/dist?rpms/foo/EL3#revision"
        scm = SCM(url)
        scm.assert_allowed(self.config)
        scm.checkout(self.tempdir, session=self.session,
                     uploadpath=self.uploadpath, logfile=self.logfile)

        source = scm.get_source()
        self.assertEqual(source, {'url': url, 'source': url})
