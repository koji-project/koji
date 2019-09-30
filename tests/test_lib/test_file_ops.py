from __future__ import absolute_import

try:
    import unittest2 as unittest
except ImportError:
    import unittest

import mock
import errno

from koji import ensuredir


class TestEnsureDir(unittest.TestCase):
    @mock.patch('os.mkdir')
    @mock.patch('os.path.exists')
    @mock.patch('os.path.isdir')
    def test_ensuredir_errors(self, mock_isdir, mock_exists, mock_mkdir):
        mock_exists.return_value = False
        with self.assertRaises(OSError) as cm:
            ensuredir('/')
        self.assertEqual(cm.exception.args[0], 'root directory missing? /')
        mock_mkdir.assert_not_called()

        mock_exists.return_value = True
        mock_isdir.return_value = False
        with self.assertRaises(OSError) as cm:
            ensuredir('/path/foo/bar')
        self.assertEqual(cm.exception.args[0],
                         'Not a directory: /path/foo/bar')
        mock_mkdir.assert_not_called()

        mock_exists.return_value = False
        mock_isdir.return_value = False
        mock_mkdir.side_effect = OSError(errno.EEXIST, 'error msg')
        with self.assertRaises(OSError) as cm:
            ensuredir('path')
        self.assertEqual(cm.exception.args[0], errno.EEXIST)
        mock_mkdir.assert_called_once_with('path')

        mock_mkdir.reset_mock()
        mock_mkdir.side_effect = OSError(errno.EEXIST, 'error msg')
        mock_isdir.return_value = True
        ensuredir('path')
        mock_mkdir.assert_called_once_with('path')

    @mock.patch('os.mkdir')
    @mock.patch('os.path.exists')
    @mock.patch('os.path.isdir')
    def test_ensuredir(self, mock_isdir, mock_exists, mock_mkdir):
        mock_exists.side_effect = [False, False, True]
        mock_isdir.return_value = True
        ensuredir('/path/foo/bar/')
        self.assertEqual(mock_exists.call_count, 3)
        self.assertEqual(mock_isdir.call_count, 1)
        mock_mkdir.assert_has_calls([mock.call('/path/foo'),
                                     mock.call('/path/foo/bar')])
