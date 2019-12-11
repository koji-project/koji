from __future__ import absolute_import
import mock
import six

from mock import call
from koji_cli.commands import handle_import_cg
from . import utils

import os

try:
    import unittest2 as unittest
except ImportError:
    import unittest


class TestImportCG(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def mock_os_path_exists(self, filepath):
        if filepath in self.custom_os_path_exists:
            return self.custom_os_path_exists[filepath]
        return self.os_path_exists(filepath)

    def setUp(self):
        self.custom_os_path_exists = {}
        self.os_path_exists = os.path.exists
        self.error_format = """Usage: %s import-cg [options] <metadata_file> <files_dir>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands._progress_callback')
    @mock.patch('koji_cli.commands.unique_path')
    @mock.patch('koji_cli.commands._running_in_bg', return_value=False)
    @mock.patch('koji_cli.commands.linked_upload')
    @mock.patch('koji_cli.commands.activate_session')
    @mock.patch('koji_cli.commands.json')
    def test_handle_import_cg(
            self,
            json_mock,
            activate_session_mock,
            linked_upload_mock,
            running_in_bg_mock,
            unique_path_mock,
            progress_callback_mock,
            stdout):
        """Test handle_import_cg function"""
        arguments = ['fake-metafile', '/path/to/files/']
        options = mock.MagicMock()
        session = mock.MagicMock()
        expected = ''
        fake_srv_path = '/path/to/server/cli-import'

        metadata = {
            'output': [
                {'relpath': '/real/path', 'filename': 'file-1'},
                {'relpath': '/real/path', 'filename': 'file-2'}
            ]
        }

        #
        # we just need to change original os.path.exists behavior, if the input
        # is matched return the value we expected.
        self.custom_os_path_exists = dict(('%(relpath)s/%(filename)s' % v, True)
                                          for v in metadata['output'])

        # setup and start os.path.exists patch
        os_path_exists_patch = mock.patch('os.path.exists',
                                          new=self.mock_os_path_exists)
        os_path_exists_patch.start()

        def gen_value(fmt, callback):
            calls, expect = [], ''
            for item in metadata['output']:
                filepath = "%(relpath)s/%(filename)s" % item
                calls.append(call(filepath,
                                  item['relpath'],
                                  callback=callback))
                expect += fmt % filepath + "\n"
            return calls, expect

        json_mock.load.return_value = metadata
        unique_path_mock.return_value = fake_srv_path

        # Case 1, running in fg, progress on
        with mock.patch(utils.get_builtin_open()):
            handle_import_cg(options, session, arguments)

        calls, expected = gen_value("Uploading %s\n", progress_callback_mock)
        self.assert_console_message(stdout, expected)
        linked_upload_mock.assert_not_called()
        session.uploadWrapper.assert_has_calls(calls)
        session.CGImport.assert_called_with(metadata, fake_srv_path, None)

        # Case 2, running in fg, progress off
        with mock.patch(utils.get_builtin_open()):
            handle_import_cg(options, session, arguments + ['--noprogress'])

        calls, expected = gen_value("Uploading %s", None)
        self.assert_console_message(stdout, expected)
        linked_upload_mock.assert_not_called()
        session.uploadWrapper.assert_has_calls(calls)
        session.CGImport.assert_called_with(metadata, fake_srv_path, None)

        # reset mocks
        linked_upload_mock.reset_mock()
        session.uploadWrapper.reset_mock()
        session.CGImport.reset_mock()

        # Case 3, --test option
        with mock.patch(utils.get_builtin_open()):
            handle_import_cg(options, session, arguments + ['--test'])

        linked_upload_mock.assert_not_called()
        session.uploadWrapper.assert_not_called()
        session.CGImport.assert_not_called()

        calls = [call("%(relpath)s/%(filename)s" % item, item['relpath'])
                 for item in metadata['output']]

        # Case 4, --link option
        with mock.patch(utils.get_builtin_open()):
            handle_import_cg(options, session, arguments + ['--link'])

        linked_upload_mock.assert_has_calls(calls)
        session.uploadWrapper.assert_not_called()
        session.CGImport.assert_called_with(metadata, fake_srv_path, None)

        # make sure there is no message on output
        self.assert_console_message(stdout, '')

        # stop os.path.exists patch
        os_path_exists_patch.stop()

    def test_handle_import_argument_test(self):
        """Test handle_import_cg function without arguments"""
        arguments = ['fake-metafile', '/path/to/files/']
        options = mock.MagicMock()
        session = mock.MagicMock()

        # Case 1. empty argument
        expected = self.format_error_message(
            "Please specify metadata files directory")

        self.assert_system_exit(
            handle_import_cg,
            options,
            session,
            [],
            stderr=expected,
            activate_session=None)

        # Case 2. JSON module does not exist
        expected = self.format_error_message('Unable to find json module')
        with mock.patch('koji_cli.commands.json', new=None):
            self.assert_system_exit(
                handle_import_cg,
                options,
                session,
                arguments,
                stderr=expected,
                activate_session=None)

        metadata = {
            'output': [
                {'metadata_only': True},
                {'relpath': '/real/path', 'filename': 'filename'}
            ]
        }

        #
        # we just need to change original os.path.exists behavior, if the input
        # is matched return the value we expected.
        self.custom_os_path_exists['/real/path/filename'] = False

        with mock.patch(utils.get_builtin_open()):
            with mock.patch('os.path.exists', new=self.mock_os_path_exists):
                with mock.patch('koji_cli.commands.json') as json_mock:

                    # Case 3. metafile doesn't have output section
                    json_mock.load.return_value = {}
                    expected = "Metadata contains no output\n"
                    self.assert_system_exit(
                        handle_import_cg,
                        options,
                        session,
                        arguments,
                        stdout=expected,
                        exit_code=1)

                    # Case 4. path not exist
                    file_path = '%(relpath)s/%(filename)s' % metadata['output'][1]
                    json_mock.load.return_value = metadata
                    expected = self.format_error_message(
                        "No such file: %s" % file_path)
                    self.assert_system_exit(
                        handle_import_cg,
                        options,
                        session,
                        arguments,
                        stderr=expected)

    def test_handle_import_cg_help(self):
        """Test handle_import_cg help message"""
        self.assert_help(
            handle_import_cg,
            """Usage: %s import-cg [options] <metadata_file> <files_dir>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help     show this help message and exit
  --noprogress   Do not display progress of the upload
  --link         Attempt to hardlink instead of uploading
  --test         Don't actually import
  --token=TOKEN  Build reservation token
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
