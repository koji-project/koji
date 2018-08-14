import copy
import unittest
import mock
import os
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji
import kojihub


class TestRPMDiff(unittest.TestCase):

    @mock.patch('koji.rpmdiff.Rpmdiff')
    def test_rpmdiff_empty_invocation(self, Rpmdiff):
        kojihub.rpmdiff('basepath', [], hashes={})
        Rpmdiff.assert_not_called()
        kojihub.rpmdiff('basepath', ['foo'], hashes={})
        Rpmdiff.assert_not_called()

    @mock.patch('koji.rpmdiff.Rpmdiff')
    def test_rpmdiff_simple_success(self, Rpmdiff):
        d = mock.MagicMock()
        d.differs.return_value = False
        Rpmdiff.return_value = d
        self.assertFalse(kojihub.rpmdiff('basepath', ['12/1234/foo', '23/2345/bar'], hashes={}))
        Rpmdiff.assert_called_once_with('basepath/12/1234/foo', 'basepath/23/2345/bar', ignore='S5TN')

    @mock.patch('koji.rpmdiff.Rpmdiff')
    def test_rpmdiff_simple_failure(self, Rpmdiff):
        d = mock.MagicMock()
        d.differs.return_value = True
        Rpmdiff.return_value = d
        with self.assertRaises(koji.BuildError):
            kojihub.rpmdiff('basepath', ['12/1234/foo', '13/1345/bar'], hashes={})
        Rpmdiff.assert_called_once_with('basepath/12/1234/foo', 'basepath/13/1345/bar', ignore='S5TN')
        d.textdiff.assert_called_once_with()

    def test_rpmdiff_real_target(self):
        data_path = os.path.abspath("tests/test_hub/data/rpms")

        # the only differences between rpm1 and rpm2 are 1) create time 2) file name
        rpm1 = os.path.join(data_path, 'test-pkg-1.0.0-1.el7.noarch.rpm')
        rpm2 = os.path.join(data_path, 'test-pkg-1.0.0-1.fc24.noarch.rpm')

        diff_output = "..........T /usr/share/test-pkg/test-doc01.txt\n" + \
                      "..........T /usr/share/test-pkg/test-doc02.txt\n" + \
                      "..........T /usr/share/test-pkg/test-doc03.txt\n" + \
                      "..........T /usr/share/test-pkg/test-doc04.txt"

        # case 1. no ignore option, timestamp is different
        # perform twice check to verify issue: #994
        for _ in range(0, 2):
            d = koji.rpmdiff.Rpmdiff(rpm1, rpm2)
            self.assertEqual(d.textdiff(), diff_output)

        # case 2. ignore timestamp, two rpms should be the same
        # perform twice check to verify issue: #994
        for r in range(0, 2):
            d = koji.rpmdiff.Rpmdiff(rpm1, rpm2, ignore='S5TN')
            self.assertEqual(d.textdiff(), '')

    def test_rpmdiff_size(self):
        data_path = os.path.abspath("tests/test_hub/data/rpms")

        # the only differences between rpm1 and rpm2 are 1) create time 2) file name
        rpm1 = os.path.join(data_path, 'different_size_a.noarch.rpm')
        rpm2 = os.path.join(data_path, 'different_size_b.noarch.rpm')

        diff_output = "S.5.......T /bin/test"

        # case 1. no ignore option, timestamp is different
        # perform twice check to verify issue: #994
        for _ in range(0, 2):
            d = koji.rpmdiff.Rpmdiff(rpm1, rpm2)
            self.assertEqual(d.textdiff(), diff_output)

        # case 2. ignore timestamp, two rpms should be the same
        # perform twice check to verify issue: #994
        for r in range(0, 2):
            d = koji.rpmdiff.Rpmdiff(rpm1, rpm2, ignore='S5TN')
            self.assertEqual(d.textdiff(), '')

class TestCheckNoarchRpms(unittest.TestCase):
    @mock.patch('kojihub.rpmdiff')
    def test_check_noarch_rpms_empty_invocation(self, rpmdiff):
        originals = ['foo', 'bar']
        result = kojihub.check_noarch_rpms('basepath', copy.copy(originals))
        self.assertEquals(result, originals)

    @mock.patch('kojihub.rpmdiff')
    def test_check_noarch_rpms_simple_invocation(self, rpmdiff):
        originals = ['12/1234/foo.noarch.rpm', '23/2345/foo.noarch.rpm']
        result = kojihub.check_noarch_rpms('basepath', copy.copy(originals))
        self.assertEquals(result, originals[0:1])
        self.assertEquals(len(rpmdiff.mock_calls), 1)

    @mock.patch('kojihub.rpmdiff')
    def test_check_noarch_rpms_with_duplicates(self, rpmdiff):
        originals = [
            'bar.noarch.rpm',
            'bar.noarch.rpm',
            'bar.noarch.rpm',
        ]
        result = kojihub.check_noarch_rpms('basepath', copy.copy(originals))
        self.assertEquals(result, ['bar.noarch.rpm'])
        rpmdiff.assert_called_once_with('basepath', originals, hashes={})

    @mock.patch('kojihub.rpmdiff')
    def test_check_noarch_rpms_with_mixed(self, rpmdiff):
        originals = [
            'foo.x86_64.rpm',
            'bar.x86_64.rpm',
            'bar.noarch.rpm',
            'bar.noarch.rpm',
        ]
        result = kojihub.check_noarch_rpms('basepath', copy.copy(originals))
        self.assertEquals(result, [
            'foo.x86_64.rpm', 'bar.x86_64.rpm', 'bar.noarch.rpm'
        ])
        rpmdiff.assert_called_once_with(
            'basepath',
            ['bar.noarch.rpm', 'bar.noarch.rpm'],
            hashes={}
        )
