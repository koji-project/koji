from __future__ import absolute_import
import copy
import mock
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
