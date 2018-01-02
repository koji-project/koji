import copy
import unittest
import mock

import koji
import kojihub


class TestRPMDiff(unittest.TestCase):

    @mock.patch('kojihub._rpmdiff.Rpmdiff')
    def test_rpmdiff_empty_invocation(self, Rpmdiff):
        kojihub.rpmdiff('basepath', [])
        Rpmdiff.assert_not_called()
        kojihub.rpmdiff('basepath', ['foo'])
        Rpmdiff.assert_not_called()

    @mock.patch('kojihub._rpmdiff.Rpmdiff')
    def test_rpmdiff_simple_success(self, Rpmdiff):
        d = mock.MagicMock()
        d.differs.return_value = False
        Rpmdiff.return_value = d
        self.assertFalse(kojihub.rpmdiff('basepath', ['foo', 'bar']))
        Rpmdiff.assert_called_once_with('basepath/foo', 'basepath/bar', ignore='S5TN')

    @mock.patch('kojihub._rpmdiff.Rpmdiff')
    def test_rpmdiff_simple_failure(self, Rpmdiff):
        d = mock.MagicMock()
        d.differs.return_value = True
        Rpmdiff.return_value = d
        with self.assertRaises(koji.BuildError):
            kojihub.rpmdiff('basepath', ['foo', 'bar'])
        Rpmdiff.assert_called_once_with('basepath/foo', 'basepath/bar', ignore='S5TN')
        d.textdiff.assert_called_once_with()

class TestCheckNoarchRpms(unittest.TestCase):
    @mock.patch('kojihub.rpmdiff')
    def test_check_noarch_rpms_empty_invocation(self, rpmdiff):
        originals = ['foo', 'bar']
        result = kojihub.check_noarch_rpms('basepath', copy.copy(originals))
        self.assertEquals(result, originals)

    @mock.patch('kojihub.rpmdiff')
    def test_check_noarch_rpms_simple_invocation(self, rpmdiff):
        originals = ['foo.noarch.rpm', 'bar.noarch.rpm']
        result = kojihub.check_noarch_rpms('basepath', copy.copy(originals))
        self.assertEquals(result, originals)
        self.assertEquals(len(rpmdiff.mock_calls), 2)

    @mock.patch('kojihub.rpmdiff')
    def test_check_noarch_rpms_with_duplicates(self, rpmdiff):
        originals = [
            'bar.noarch.rpm',
            'bar.noarch.rpm',
            'bar.noarch.rpm',
        ]
        result = kojihub.check_noarch_rpms('basepath', copy.copy(originals))
        self.assertEquals(result, ['bar.noarch.rpm'])
        rpmdiff.assert_called_once_with('basepath', originals)

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
        rpmdiff.assert_called_once_with('basepath', [
            'bar.noarch.rpm', 'bar.noarch.rpm'
        ])
