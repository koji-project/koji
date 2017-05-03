from __future__ import absolute_import
import copy
import unittest
import mock

import koji
import kojihub


class TestRPMDiff(unittest.TestCase):

    @mock.patch('kojihub.subprocess')
    def test_rpmdiff_empty_invocation(self, subprocess):
        process = mock.MagicMock()
        subprocess.Popen.return_value = process
        kojihub.rpmdiff('basepath', [])
        self.assertEquals(len(subprocess.Popen.mock_calls), 0)
        kojihub.rpmdiff('basepath', ['foo'])
        self.assertEquals(len(subprocess.Popen.mock_calls), 0)

    @mock.patch('kojihub.subprocess')
    def test_rpmdiff_simple_success(self, subprocess):
        process = mock.MagicMock()
        subprocess.Popen.return_value = process
        process.wait.return_value = 0
        kojihub.rpmdiff('basepath', ['foo', 'bar'])
        self.assertEquals(len(subprocess.Popen.call_args_list), 1)

    @mock.patch('kojihub.subprocess')
    def test_rpmdiff_simple_failure(self, subprocess):
        process = mock.MagicMock()
        subprocess.Popen.return_value = process
        process.wait.return_value = 1
        with self.assertRaises(koji.BuildError):
            kojihub.rpmdiff('basepath', ['foo', 'bar'])

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
