from __future__ import absolute_import
import mock
import os
try:
    import unittest2 as unittest
except ImportError:
    import unittest
import koji
import kojihub


class TestGetRPMDeps(unittest.TestCase):
    @mock.patch('kojihub.get_rpm')
    @mock.patch('kojihub.get_build')
    @mock.patch('koji.pathinfo')
    def test_getRPMDeps(self, pi, build, rpm):
        pi.build.return_value = os.path.join(os.path.dirname(__file__), '../test_lib/data/rpms')
        pi.rpm.return_value = 'test-deps-1-1.fc24.x86_64.rpm'
        getRPMDeps = kojihub.RootExports().getRPMDeps
        res = getRPMDeps('')
        # limit test for rpm < 4.12
        if koji.RPM_SUPPORTS_OPTIONAL_DEPS:
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
