import io
import shutil
import tempfile
import urllib.parse
import unittest
from unittest import mock

import koji
from kojihub import kojihub

"""
This test involves both client and hub code.
Since hub code has higher requirements, we group it there.
"""


def get_callMethod(self):
    # create a function to replace ClientSession._callMethod
    # self is the session instance

    def my_callMethod(name, args, kwargs=None, retry=True):
        # we only handle the methods that fastUpload will use
        handler, headers, request = self._prepCall(name, args, kwargs)
        self.retries = 0
        if name == 'rawUpload':
            parts = urllib.parse.urlparse(handler)
            query = parts[4]
            environ = {
                'QUERY_STRING': query,
                'wsgi.input': io.BytesIO(request),
                'CONTENT_LENGTH': len(request),
            }
            return kojihub.handle_upload(environ)
        elif name == 'checkUpload':
            exports = kojihub.RootExports()
            return exports.checkUpload(*args, **kwargs)
        # else
        raise ValueError(f'Unexected call {name}')

    return my_callMethod


class TestHandleUpload(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.pathinfo = koji.PathInfo(self.tempdir)
        mock.patch('koji.pathinfo', new=self.pathinfo).start()
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.logged_in = True
        self.context.session.user_id = 1
        self.session = koji.ClientSession('https://koji.example.com/NOTUSED')
        self.session._callMethod = get_callMethod(self.session)

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        mock.patch.stopall()

    def test_upload_client(self):
        # write a test file
        contents = b'Hello World. Upload me.\n' * 100
        orig = f'{self.tempdir}/orig.txt'
        with open(orig, 'wb') as fp:
            fp.write(contents)
        sinfo = {'session-id': '123', 'session-key': '456', 'callnum': 1}
        self.session.setSession(sinfo)  # marks logged in

        self.session.fastUpload(orig, 'testpath', blocksize=137)

        # files should be identical
        dup = f'{self.tempdir}/work/testpath/orig.txt'
        with open(dup, 'rb') as fp:
            check = fp.read()
        self.assertEqual(check, contents)

    def test_upload_client_overwrite(self):
        # same as above, but with overwrite flag
        contents = b'Hello World. Upload me.\n' * 100
        orig = f'{self.tempdir}/orig.txt'
        with open(orig, 'wb') as fp:
            fp.write(contents)
        sinfo = {'session-id': '123', 'session-key': '456', 'callnum': 1}
        self.session.setSession(sinfo)  # marks logged in

        self.session.fastUpload(orig, 'testpath', blocksize=137, overwrite=True)

        # files should be identical
        dup = f'{self.tempdir}/work/testpath/orig.txt'
        with open(dup, 'rb') as fp:
            check = fp.read()
        self.assertEqual(check, contents)

# the end
