import os
import io
from unittest import mock
import shutil
import tempfile
import urllib.parse
import unittest

from kojihub import kojihub
import koji
from koji import GenericError


class TestHandleUpload(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.pathinfo = koji.PathInfo(self.tempdir)
        mock.patch('koji.pathinfo', new=self.pathinfo).start()
        self.lookup_name = mock.patch('kojihub.kojihub.lookup_name').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.logged_in = True
        self.context.session.user_id = 1

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        mock.patch.stopall()

    def test_simple_upload(self):
        environ = {}
        args = {
            'filename': 'hello.txt',
            'filepath': 'FOO',
            'fileverify': 'adler32',
            'offset': '0',
        }
        environ['QUERY_STRING'] = urllib.parse.urlencode(args)
        contents = b'hello world\n'
        environ['wsgi.input'] = io.BytesIO(contents)

        # upload
        kojihub.handle_upload(environ)

        # verify
        fn = f'{self.tempdir}/work/FOO/hello.txt'
        self.assertEqual(contents, open(fn, 'rb').read())

    def test_no_overwrite(self):
        environ = {}
        args = {
            # overwrite should default to False
            'filename': 'hello.txt',
            'filepath': 'FOO',
            'fileverify': 'adler32',
            'offset': '0',
        }
        environ['QUERY_STRING'] = urllib.parse.urlencode(args)
        contents = b'hello world\n'
        environ['wsgi.input'] = io.BytesIO(contents)
        fn = f'{self.tempdir}/work/FOO/hello.txt'
        koji.ensuredir(os.path.dirname(fn))
        with open(fn, 'wt') as fp:
            fp.write('already exists')

        # upload
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.handle_upload(environ)

        # verify error
        self.assertIn('upload path exists', str(ex.exception))

    def test_no_symlink(self):
        environ = {}
        args = {
            # overwrite should default to False
            'filename': 'hello.txt',
            'filepath': 'FOO',
            'fileverify': 'adler32',
            'offset': '0',
        }
        environ['QUERY_STRING'] = urllib.parse.urlencode(args)
        fn = f'{self.tempdir}/work/FOO/hello.txt'
        koji.ensuredir(os.path.dirname(fn))
        os.symlink('link_target', fn)

        # upload
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.handle_upload(environ)

        # verify error
        self.assertIn('destination is a symlink', str(ex.exception))

    def test_no_nonfile(self):
        environ = {}
        args = {
            # overwrite should default to False
            'filename': 'hello.txt',
            'filepath': 'FOO',
            'fileverify': 'adler32',
            'offset': '0',
        }
        environ['QUERY_STRING'] = urllib.parse.urlencode(args)
        fn = f'{self.tempdir}/work/FOO/hello.txt'
        koji.ensuredir(os.path.dirname(fn))
        os.mkdir(fn)

        # upload
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.handle_upload(environ)

        # verify error
        self.assertIn('destination not a file', str(ex.exception))

    def test_login_required(self):
        environ = {}
        self.context.session.logged_in = False

        with self.assertRaises(koji.ActionNotAllowed):
            kojihub.handle_upload(environ)

    def test_retry(self):
        # uploading the same chunk twice should be fine
        environ = {}
        args = {
            'filename': 'hello.txt',
            'filepath': 'FOO',
            'fileverify': 'adler32',
            'offset': '0',
        }
        environ['QUERY_STRING'] = urllib.parse.urlencode(args)
        contents = b'hello world\nthis is line two'
        chunks = contents.splitlines(keepends=True)

        # chunk 0
        environ['wsgi.input'] = io.BytesIO(chunks[0])
        kojihub.handle_upload(environ)

        # chunk 1
        environ['wsgi.input'] = io.BytesIO(chunks[1])
        args['offset'] = str(len(chunks[0]))
        environ['QUERY_STRING'] = urllib.parse.urlencode(args)
        kojihub.handle_upload(environ)

        # chunk 1, again
        environ['wsgi.input'] = io.BytesIO(chunks[1])
        kojihub.handle_upload(environ)

        # verify
        fn = f'{self.tempdir}/work/FOO/hello.txt'
        self.assertEqual(contents, open(fn, 'rb').read())

    def test_no_truncate(self):
        # uploading a chunk out of order without overwrite should:
        # 1. not truncate
        # 2. error
        environ = {}
        args = {
            'filename': 'hello.txt',
            'filepath': 'FOO',
            'fileverify': 'adler32',
            'offset': '0',
        }
        environ['QUERY_STRING'] = urllib.parse.urlencode(args)
        contents = b'hello world\nthis is line two\nthis is line three'
        chunks = contents.splitlines(keepends=True)

        # chunk 0
        environ['wsgi.input'] = io.BytesIO(chunks[0])
        kojihub.handle_upload(environ)

        # chunk 1
        environ['wsgi.input'] = io.BytesIO(chunks[1])
        args['offset'] = str(len(chunks[0]))
        environ['QUERY_STRING'] = urllib.parse.urlencode(args)
        kojihub.handle_upload(environ)

        # chunk 2
        environ['wsgi.input'] = io.BytesIO(chunks[2])
        args['offset'] = str(len(chunks[0]) + len(chunks[1]))
        environ['QUERY_STRING'] = urllib.parse.urlencode(args)
        kojihub.handle_upload(environ)

        # chunk 1, again
        environ['wsgi.input'] = io.BytesIO(chunks[1])
        args['offset'] = str(len(chunks[0]))
        environ['QUERY_STRING'] = urllib.parse.urlencode(args)
        with self.assertRaises(koji.GenericError) as ex:
            kojihub.handle_upload(environ)

        # verify
        self.assertIn('Incorrect upload length', str(ex.exception))
        # previous upload contents should still be there
        fn = f'{self.tempdir}/work/FOO/hello.txt'
        self.assertEqual(contents, open(fn, 'rb').read())

    def test_truncate(self):
        # uploading a chunk with overwrite SHOULD truncate:
        environ = {}
        args = {
            'filename': 'hello.txt',
            'filepath': 'FOO',
            'fileverify': 'adler32',
            'offset': '0',
        }
        environ['QUERY_STRING'] = urllib.parse.urlencode(args)
        contents1 = b'hello world\nthis is line two\nthis is line three'
        contents2 = b'hello world\n'

        # pass1
        environ['wsgi.input'] = io.BytesIO(contents1)
        kojihub.handle_upload(environ)

        # pass2
        args['overwrite'] = '1'
        environ['QUERY_STRING'] = urllib.parse.urlencode(args)
        environ['wsgi.input'] = io.BytesIO(contents2)
        kojihub.handle_upload(environ)

        # verify
        fn = f'{self.tempdir}/work/FOO/hello.txt'
        self.assertEqual(contents2, open(fn, 'rb').read())
# the end
