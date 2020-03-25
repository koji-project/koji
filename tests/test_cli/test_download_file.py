from __future__ import absolute_import
import mock
import six
import shutil
import tempfile
import os
import requests_mock
import requests
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.lib import download_file, _download_progress

def mock_open():
    """Return the right patch decorator for open"""
    if six.PY2:
        return mock.patch('__builtin__.open')
    else:
        return mock.patch('builtins.open')


class TestDownloadFile(unittest.TestCase):
    # Show long diffs in error output...
    maxDiff = None

    def reset_mock(self):
        self.stdout.seek(0)
        self.stdout.truncate()
        self.stderr.seek(0)
        self.stderr.truncate()
        self.requests_get.reset_mock()

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.filename = self.tempdir + "/filename"
        self.stdout = mock.patch('sys.stdout', new_callable=six.StringIO).start()
        self.stderr = mock.patch('sys.stderr', new_callable=six.StringIO).start()
        self.requests_get = mock.patch('requests.get', create=True, name='requests.get').start()
        # will work when contextlib.closing will be removed in future
        #self.requests_get = self.requests_get.return_value.__enter__

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.tempdir)

    def test_handle_download_file_dir(self):
        with self.assertRaises(IOError) as cm:
            download_file("http://url", self.tempdir)
        actual = self.stdout.getvalue()
        expected = 'Downloading: %s\n' % self.tempdir
        self.assertMultiLineEqual(actual, expected)
        if isinstance(cm.exception, tuple):
            self.assertEqual(cm.exception[0], 21)
            self.assertEqual(cm.exception[1], 'Is a directory')
        else:
            self.assertEqual(cm.exception.args, (21, 'Is a directory'))

    @mock_open()
    def test_handle_download_file(self, m_open):
        self.reset_mock()
        response = mock.MagicMock()
        self.requests_get.return_value = response
        response.headers.get.return_value = '5' # content-length
        response.iter_content.return_value = ['abcde']

        rv = download_file("http://url", self.filename)

        actual = self.stdout.getvalue()
        expected = 'Downloading: %s\n[====================================] 100%%     5.00 B\r\n' % self.filename
        self.assertMultiLineEqual(actual, expected)

        self.requests_get.assert_called_once()
        m_open.assert_called_once()
        response.headers.get.assert_called_once()
        response.iter_content.assert_called_once()
        self.assertIsNone(rv)

    @mock_open()
    def test_handle_download_file_undefined_length(self, m_open):
        self.reset_mock()
        response = mock.MagicMock()
        self.requests_get.return_value = response
        response.headers.get.return_value = None # content-length
        response.iter_content.return_value = ['a' * 65536, 'b' * 65536]

        rv = download_file("http://url", self.filename)

        actual = self.stdout.getvalue()
        expected = 'Downloading: %s\n[                                    ] ???%%  64.00 KiB\r[                                    ] ???%% 128.00 KiB\r[====================================] 100%% 128.00 KiB\r\n' % self.filename
        self.assertMultiLineEqual(actual, expected)

        self.requests_get.assert_called_once()
        m_open.assert_called_once()
        response.headers.get.assert_called_once()
        response.iter_content.assert_called_once()
        self.assertIsNone(rv)


    def test_handle_download_file_with_size(self):
        rv = download_file("http://url", self.filename, size=10, num=8)
        actual = self.stdout.getvalue()
        expected = 'Downloading [8/10]: %s\n\n' % self.filename
        self.assertMultiLineEqual(actual, expected)
        self.requests_get.assert_called_once()
        self.assertIsNone(rv)

    def test_handle_download_file_quiet_noprogress(self):
        download_file("http://url", self.filename, quiet=True, noprogress=False)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)

        self.reset_mock()
        download_file("http://url", self.filename, quiet=True, noprogress=True)
        actual = self.stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)

        self.reset_mock()
        download_file("http://url", self.filename, quiet=False, noprogress=True)
        actual = self.stdout.getvalue()
        expected = 'Downloading: %s\n' % self.filename
        self.assertMultiLineEqual(actual, expected)

    '''
    possible tests
    - handling redirect headers
    - http vs https
    '''

class TestDownloadProgress(unittest.TestCase):
    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.stdout = mock.patch('sys.stdout', new_callable=six.StringIO).start()

    def tearDown(self):
        mock.patch.stopall()

    def test_download_progress(self):
        _download_progress(0, 0)
        _download_progress(1024 * 92, 1024)
        _download_progress(1024 * 1024 * 23, 1024 * 1024 * 11)
        _download_progress(1024 * 1024 * 1024 * 35, 1024 * 1024 * 1024 * 30)
        _download_progress(318921, 318921)
        actual = self.stdout.getvalue()
        expected = '[                                    ] ???%     0.00 B\r' + \
                   '[                                    ]   1%   1.00 KiB\r' + \
                   '[=================                   ]  47%  11.00 MiB\r' + \
                   '[==============================      ]  85%  30.00 GiB\r' + \
                   '[====================================] 100% 311.45 KiB\r'
        self.assertMultiLineEqual(actual, expected)


class TestDownloadFileError(unittest.TestCase):
    """Check error status code and text in download_file."""
    filename = '/tmp/tmp-download'

    @requests_mock.Mocker()
    def test_handle_download_file_error_404(self, m):
        m.get("http://url", text='Not Found\n', status_code=404)
        with self.assertRaises(requests.HTTPError):
            download_file("http://url", self.filename)
        try:
            os.unlink(self.filename)
        except Exception:
            pass

    @requests_mock.Mocker()
    def test_handle_download_file_error_500(self, m):
        m.get("http://url", text='Internal Server Error\n', status_code=500)
        with self.assertRaises(requests.HTTPError):
            download_file("http://url", self.filename)
        try:
            os.unlink(self.filename)
        except Exception:
            pass

if __name__ == '__main__':
    unittest.main()
