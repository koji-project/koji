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
            "git://server/foo.git?params=not_allowed",
            "git://server#asdasd",  # no path
            "git://server/foo.git",  # no fragment
            "http://localhost/foo.html",
            "foo-1.1-1.src.rpm",
            "https://server/foo-1.1-1.src.rpm",
            ]
        for url in bad:
            print url
            try:
            #with self.assertRaises(koji.GenericError):
                scm = SCM(url)
            except koji.GenericError, e:
                print e
            else:
                raise Exception("fucked")

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



