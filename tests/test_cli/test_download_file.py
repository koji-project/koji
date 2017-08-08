from __future__ import absolute_import
import mock
from mock import call
import six
import shutil
import tempfile
import unittest

from koji_cli.lib import download_file, _download_progress


class TestDownloadFile(unittest.TestCase):
    # Show long diffs in error output...
    maxDiff = None

    def reset_mock(self):
        self.stdout.seek(0)
        self.stdout.truncate()
        self.stderr.seek(0)
        self.stderr.truncate()
        # self.curl.reset_mock()
        self.curlClass.reset_mock()

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.filename = self.tempdir + "/filename"
        self.stdout = mock.patch('sys.stdout', new_callable=six.StringIO).start()
        self.stderr = mock.patch('sys.stderr', new_callable=six.StringIO).start()
        self.curlClass = mock.patch('pycurl.Curl', create=True).start()
        self.curl = self.curlClass.return_value

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.tempdir)

    def test_handle_download_file_dir(self):
        with self.assertRaises(IOError) as cm:
            download_file("http://url", self.tempdir)
        actual = self.stdout.getvalue()
        expected = 'Downloading: %s\n' % self.tempdir
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(cm.exception.args, (21, 'Is a directory'))
        self.curlClass.assert_called_once()
        self.assertEqual(self.curl.setopt.call_count, 2)
        self.curl.perform.assert_not_called()

    def test_handle_download_file(self):
        rv = download_file("http://url", self.filename)
        actual = self.stdout.getvalue()
        expected = 'Downloading: %s\n\n' % self.filename
        self.assertMultiLineEqual(actual, expected)
        self.curlClass.assert_called_once()
        self.assertEqual(self.curl.setopt.call_count, 5)
        self.curl.perform.assert_called_once()
        self.curl.close.assert_called_once()
        self.assertIsNone(rv)

    def test_handle_download_file_with_size(self):
        rv = download_file("http://url", self.filename, size=10, num=8)
        actual = self.stdout.getvalue()
        expected = 'Downloading [8/10]: %s\n\n' % self.filename
        self.assertMultiLineEqual(actual, expected)
        self.curlClass.assert_called_once()
        self.assertEqual(self.curl.setopt.call_count, 5)
        self.curl.perform.assert_called_once()
        self.curl.close.assert_called_once()
        self.assertIsNone(rv)

    def test_handle_download_file_quiet_noprogress(self):
        download_file("http://url", self.filename, quiet=True, noprogress=False)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(self.curl.setopt.call_count, 3)

        self.reset_mock()
        download_file("http://url", self.filename, quiet=True, noprogress=True)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(self.curl.setopt.call_count, 3)

        self.reset_mock()
        download_file("http://url", self.filename, quiet=False, noprogress=True)
        actual = self.stdout.getvalue()
        expected = 'Downloading: %s\n' % self.filename
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(self.curl.setopt.call_count, 3)

    def test_handle_download_file_curl_version(self):
        self.curl.XFERINFOFUNCTION = None
        download_file("http://url", self.filename, quiet=False, noprogress=False)
        actual = self.stdout.getvalue()
        expected = 'Downloading: %s\n\n' % self.filename
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(self.curl.setopt.call_count, 5)
        self.curl.setopt.assert_has_calls([call(self.curl.PROGRESSFUNCTION, _download_progress)])

        self.reset_mock()
        self.curl.PROGRESSFUNCTION = None
        with self.assertRaises(SystemExit) as cm:
            download_file("http://url", self.filename, quiet=False, noprogress=False)
        actual = self.stdout.getvalue()
        expected = 'Downloading: %s\n' % self.filename
        self.assertMultiLineEqual(actual, expected)
        actual = self.stderr.getvalue()
        expected = 'Error: XFERINFOFUNCTION and PROGRESSFUNCTION are not supported by pyCurl. Quit download progress\n'
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(self.curl.setopt.call_count, 3)
        self.assertEqual(cm.exception.code, 1)



class TestDownloadProgress(unittest.TestCase):
    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.stdout = mock.patch('sys.stdout', new_callable=six.StringIO).start()

    def tearDown(self):
        mock.patch.stopall()

    def test_download_progress(self):
        _download_progress(0, 0, None, None)
        _download_progress(1024 * 92, 1024, None, None)
        _download_progress(1024 * 1024 * 23, 1024 * 1024 * 11, None, None)
        _download_progress(1024 * 1024 * 1024 * 35, 1024 * 1024 * 1024 * 30, None, None)
        _download_progress(318921, 318921, None, None)
        actual = self.stdout.getvalue()
        expected = '[                                    ]  00%     0.00 B\r' + \
                   '[                                    ]  01%   1.00 KiB\r' + \
                   '[=================                   ]  47%  11.00 MiB\r' + \
                   '[==============================      ]  85%  30.00 GiB\r' + \
                   '[====================================] 100% 311.45 KiB\r'
        self.assertMultiLineEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
