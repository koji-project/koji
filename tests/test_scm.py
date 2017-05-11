import mock
import unittest

import logging
import koji

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
        allowed = '''
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
            ]
        for url in good:
            scm = SCM(url)
            scm.assert_allowed(allowed)
        for url in bad:
            scm = SCM(url)
            with self.assertRaises(koji.BuildError):
                scm.assert_allowed(allowed)

    @mock.patch('logging.getLogger')
    def test_badrule(self, getLogger):
        allowed = '''
            bogus-entry-should-be-ignored
            goodserver:*:no
            !badserver:*
            '''
        url = "git://goodserver/path1#1234"
        scm = SCM(url)
        scm.assert_allowed(allowed)

    @mock.patch('logging.getLogger')
    def test_opts(self, getLogger):
        allowed = '''
            default:*
            nocommon:*:no
            srccmd:*:no:fedpkg,sources
            mixed:/foo/*:no
            mixed:/bar/*:yes
            mixed:/baz/*:no:fedpkg,sources
            '''

        url = "git://default/koji.git#1234"
        scm = SCM(url)
        scm.assert_allowed(allowed)
        self.assertEqual(scm.use_common, True)
        self.assertEqual(scm.source_cmd, ['make', 'sources'])

        url = "git://nocommon/koji.git#1234"
        scm = SCM(url)
        scm.assert_allowed(allowed)
        self.assertEqual(scm.use_common, False)
        self.assertEqual(scm.source_cmd, ['make', 'sources'])

        url = "git://srccmd/koji.git#1234"
        scm = SCM(url)
        scm.assert_allowed(allowed)
        self.assertEqual(scm.use_common, False)
        self.assertEqual(scm.source_cmd, ['fedpkg', 'sources'])

        url = "git://mixed/foo/koji.git#1234"
        scm = SCM(url)
        scm.assert_allowed(allowed)
        self.assertEqual(scm.use_common, False)
        self.assertEqual(scm.source_cmd, ['make', 'sources'])

        url = "git://mixed/bar/koji.git#1234"
        scm = SCM(url)
        scm.assert_allowed(allowed)
        self.assertEqual(scm.use_common, True)
        self.assertEqual(scm.source_cmd, ['make', 'sources'])

        url = "git://mixed/baz/koji.git#1234"
        scm = SCM(url)
        scm.assert_allowed(allowed)
        self.assertEqual(scm.use_common, False)
        self.assertEqual(scm.source_cmd, ['fedpkg', 'sources'])

        url = "git://mixed/koji.git#1234"
        scm = SCM(url)
        with self.assertRaises(koji.BuildError):
            scm.assert_allowed(allowed)

