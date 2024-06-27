from __future__ import absolute_import
import os
import unittest
try:
    from unittest import mock
    from unittest.mock import call
except ImportError:
    import mock
    from mock import call

import six

from koji_cli.commands import handle_import_cg
from . import utils


class TestImportCG(utils.CliTestCase):
    def mock_os_path_exists(self, filepath):
        if filepath in self.custom_os_path_exists:
            return self.custom_os_path_exists[filepath]
        return self.os_path_exists(filepath)

    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.custom_os_path_exists = {}
        self.os_path_exists = os.path.exists
        self.unique_path_mock = mock.patch('koji_cli.commands.unique_path').start()
        self.running_in_bg = mock.patch('koji_cli.commands._running_in_bg').start()
        self.running_in_bg.return_value = False
        self.linked_upload_mock = mock.patch('koji_cli.commands.linked_upload').start()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s import-cg [options] <metadata_file> <files_dir>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands._progress_callback')
    @mock.patch('koji.json')
    def test_handle_import_cg(self, json_mock, progress_callback_mock, stdout):
        """Test handle_import_cg function"""
        arguments = ['fake-metafile', '/path/to/files/']
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
        self.unique_path_mock.return_value = fake_srv_path

        # Case 1, running in fg, progress on
        with mock.patch(utils.get_builtin_open()):
            handle_import_cg(self.options, self.session, arguments)

        calls, expected = gen_value("Uploading %s\n", progress_callback_mock)
        self.assert_console_message(stdout, expected)
        self.linked_upload_mock.assert_not_called()
        self.session.uploadWrapper.assert_has_calls(calls)
        self.session.CGImport.assert_called_with(metadata, fake_srv_path, None)

        # Case 2, running in fg, progress off
        with mock.patch(utils.get_builtin_open()):
            handle_import_cg(self.options, self.session, arguments + ['--noprogress'])

        calls, expected = gen_value("Uploading %s", None)
        self.assert_console_message(stdout, expected)
        self.linked_upload_mock.assert_not_called()
        self.session.uploadWrapper.assert_has_calls(calls)
        self.session.CGImport.assert_called_with(metadata, fake_srv_path, None)

        # reset mocks
        self.linked_upload_mock.reset_mock()
        self.session.uploadWrapper.reset_mock()
        self.session.CGImport.reset_mock()

        # Case 3, --test option
        with mock.patch(utils.get_builtin_open()):
            handle_import_cg(self.options, self.session, arguments + ['--test'])

        self.linked_upload_mock.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.CGImport.assert_not_called()

        calls = [call("%(relpath)s/%(filename)s" % item, item['relpath'])
                 for item in metadata['output']]

        # Case 4, --link option
        with mock.patch(utils.get_builtin_open()):
            handle_import_cg(self.options, self.session, arguments + ['--link'])

        self.linked_upload_mock.assert_has_calls(calls)
        self.session.uploadWrapper.assert_not_called()
        self.session.CGImport.assert_called_with(metadata, fake_srv_path, None)

        # make sure there is no message on output
        self.assert_console_message(stdout, '')

        # stop os.path.exists patch
        os_path_exists_patch.stop()

    def test_handle_import_argument_test(self):
        """Test handle_import_cg function without arguments"""
        arguments = ['fake-metafile', '/path/to/files/']

        # Case 1. empty argument
        self.assert_system_exit(
            handle_import_cg,
            self.options, self.session, [],
            stderr=self.format_error_message("Please specify metadata files directory"),
            activate_session=None)

        # Case 2. JSON module does not exist
        # dropped - it is now part of stdlib

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
                with mock.patch('koji.json') as json_mock:

                    # Case 3. metafile doesn't have output section
                    json_mock.load.return_value = {}
                    self.assert_system_exit(
                        handle_import_cg,
                        self.options, self.session, arguments,
                        stderr="Metadata contains no output\n",
                        exit_code=1)

                    # Case 4. path not exist
                    file_path = '%(relpath)s/%(filename)s' % metadata['output'][1]
                    json_mock.load.return_value = metadata
                    self.assert_system_exit(
                        handle_import_cg,
                        self.options, self.session, arguments,
                        stderr=self.format_error_message("No such file: %s" % file_path),
                        exit_code=2)

    def test_handle_import_cg_help(self):
        """Test handle_import_cg help message"""
        self.assert_help(
            handle_import_cg,
            """Usage: %s import-cg [options] <metadata_file> <files_dir>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help           show this help message and exit
  --noprogress         Do not display progress of the upload
  --link               Attempt to hardlink instead of uploading
  --test               Don't actually import
  --token=TOKEN        Build reservation token
  --draft              Import as a draft
  --build-id=BUILD_ID  Reserved build id
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
