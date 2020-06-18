import mock
import os
import unittest
import koji
import kojihub


class TestGetRPMDeps(unittest.TestCase):

    @mock.patch('kojihub.get_rpm')
    def test_getRPMDeps_no_rpminfo(self, get_rpm):
        def mock_get_rpm(rpmID, strict=False):
            if strict:
                raise koji.GenericError('msg')
            else:
                return None
        get_rpm.side_effect = mock_get_rpm
        re = kojihub.RootExports().getRPMDeps(1)
        self.assertEquals(re, [])
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.RootExports().getRPMDeps(1, strict=True)
        self.assertEquals(cm.exception.args[0], 'msg')

    @mock.patch('kojihub.get_rpm', return_value={'id': 1, 'build_id': None})
    def test_getRPMDeps_external_rpm(self, get_rpm):
        re = kojihub.RootExports().getRPMDeps(1)
        self.assertEquals(re, [])
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.RootExports().getRPMDeps(1, strict=True)
        self.assertEquals(cm.exception.args[0],
                          'Can not get dependencies,'
                          ' because RPM: 1 is not internal')

    @mock.patch('kojihub.get_rpm', return_value={'id': 1, 'build_id': 1})
    @mock.patch('kojihub.get_build', return_value={'id': 1})
    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('koji.pathinfo.rpm', return_value='fakerpmrelpath')
    @mock.patch('os.path.exists', return_value=False)
    def test_getRPMDeps_no_rpmfile(self, ope, pr, pb, get_build, get_rpm):
        re = kojihub.RootExports().getRPMDeps(1)
        self.assertEquals(re, [])
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.RootExports().getRPMDeps(1, strict=True)
        self.assertEquals(cm.exception.args[0],
                          "RPM file of 1 doesn't exist")

    @mock.patch('kojihub.get_rpm')
    @mock.patch('kojihub.get_build')
    @mock.patch('koji.pathinfo')
    def test_getRPMDeps(self, pi, build, rpm):
        pi.build.return_value = os.path.join(os.path.dirname(__file__), '../test_lib/data/rpms')
        pi.rpm.return_value = 'test-deps-1-1.fc24.x86_64.rpm'
        getRPMDeps = kojihub.RootExports().getRPMDeps
        res = getRPMDeps('')
        # limit test for rpm < 4.12
        if any(koji.SUPPORTED_OPT_DEP_HDRS.values()):
            self.assertEqual(len(res), 22)
            types = set([x['type'] for x in res])
            self.assertEqual(set([koji.DEP_REQUIRE,
                                  koji.DEP_PROVIDE,
                                  koji.DEP_OBSOLETE,
                                  koji.DEP_CONFLICT,
                                  koji.DEP_SUGGEST,
                                  koji.DEP_ENHANCE,
                                  koji.DEP_SUPPLEMENT,
                                  koji.DEP_RECOMMEND,
                                  ]), types)

            # test correct mapping of names
            result = {}
            for r in res:
                result.setdefault(r['type'], set()).add(r['name'])
            self.assertTrue('require1' in result[koji.DEP_REQUIRE])
            self.assertTrue('provide1' in result[koji.DEP_PROVIDE])
            self.assertTrue('obsoletes1' in result[koji.DEP_OBSOLETE])
            self.assertTrue('conflicts1' in result[koji.DEP_CONFLICT])
            self.assertTrue('suggests1' in result[koji.DEP_SUGGEST])
            self.assertTrue('enhances1' in result[koji.DEP_ENHANCE])
            self.assertTrue('supplements1' in result[koji.DEP_SUPPLEMENT])
            self.assertTrue('recommends1' in result[koji.DEP_RECOMMEND])
        else:
            self.assertEqual(len(res), 14)
            types = set([x['type'] for x in res])
            self.assertEqual(set([koji.DEP_REQUIRE,
                                  koji.DEP_PROVIDE,
                                  koji.DEP_OBSOLETE,
                                  koji.DEP_CONFLICT,
                                  ]), types)

            # test correct mapping of names
            result = {}
            for r in res:
                result.setdefault(r['type'], set()).add(r['name'])
            self.assertTrue('require1' in result[koji.DEP_REQUIRE])
            self.assertTrue('provide1' in result[koji.DEP_PROVIDE])
            self.assertTrue('obsoletes1' in result[koji.DEP_OBSOLETE])
            self.assertTrue('conflicts1' in result[koji.DEP_CONFLICT])
