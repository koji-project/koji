import mock
import os
import unittest
import koji
import kojihub


class TestGetRPMDeps(unittest.TestCase):
    def setUp(self):
        self.exports = kojihub.RootExports()
        self.get_rpm = mock.patch('kojihub.kojihub.get_rpm').start()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()

    def test_getRPMDeps_no_rpminfo(self):
        def mock_get_rpm(rpmID, strict=False):
            if strict:
                raise koji.GenericError('msg')
            else:
                return None
        self.get_rpm.side_effect = mock_get_rpm
        re = self.exports.getRPMDeps(1)
        self.assertEqual(re, [])
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getRPMDeps(1, strict=True)
        self.assertEqual(cm.exception.args[0], 'msg')

    def test_getRPMDeps_external_rpm(self):
        self.get_rpm.return_value = {'id': 1, 'build_id': None}
        re = self.exports.getRPMDeps(1)
        self.assertEqual(re, [])
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getRPMDeps(1, strict=True)
        self.assertEqual(cm.exception.args[0],
                         'Can not get dependencies, because RPM: 1 is not internal')

    @mock.patch('koji.pathinfo.build', return_value='fakebuildpath')
    @mock.patch('koji.pathinfo.rpm', return_value='fakerpmrelpath')
    @mock.patch('os.path.exists', return_value=False)
    def test_getRPMDeps_no_rpmfile(self, ope, pr, pb):
        self.get_rpm.return_value = {'id': 1, 'build_id': 1}
        self.get_build.return_value = {'id': 1}
        re = self.exports.getRPMDeps(1)
        self.assertEqual(re, [])
        with self.assertRaises(koji.GenericError) as cm:
            self.exports.getRPMDeps(1, strict=True)
        self.assertEqual(cm.exception.args[0], "RPM file of 1 doesn't exist")

    @mock.patch('koji.pathinfo')
    def test_getRPMDeps(self, pi):
        pi.build.return_value = os.path.join(os.path.dirname(__file__), '../test_lib/data/rpms')
        pi.rpm.return_value = 'test-deps-1-1.fc24.x86_64.rpm'
        getRPMDeps = self.exports.getRPMDeps
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
