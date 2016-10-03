import mock
import os
import unittest

import koji
import kojihub


class TestGetRPMDeps(unittest.TestCase):
    @mock.patch('kojihub.get_rpm')
    @mock.patch('kojihub.get_build')
    @mock.patch('koji.pathinfo')
    def test_getRPMDeps(self, pi, build, rpm):
        pi.build.return_value = os.path.join(os.path.dirname(__file__), '../data/rpms')
        pi.rpm.return_value = 'test-deps-1-1.fc24.x86_64.rpm'
        getRPMDeps = kojihub.RootExports().getRPMDeps
        res = getRPMDeps('')
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
        self.assertIn('require1', result[koji.DEP_REQUIRE])
        self.assertIn('provide1', result[koji.DEP_PROVIDE])
        self.assertIn('obsoletes1', result[koji.DEP_OBSOLETE])
        self.assertIn('conflicts1', result[koji.DEP_CONFLICT])
        self.assertIn('suggests1', result[koji.DEP_SUGGEST])
        self.assertIn('enhances1', result[koji.DEP_ENHANCE])
        self.assertIn('supplements1', result[koji.DEP_SUPPLEMENT])
        self.assertIn('recommends1', result[koji.DEP_RECOMMEND])
