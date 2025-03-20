from __future__ import absolute_import
import json
import os
import shutil
import tempfile
try:
    from unittest import mock
except ImportError:
    import mock

import koji
from koji_cli.commands import handle_import_cg, _progress_callback
from . import utils


class TestImportCG(utils.CliTestCase):

    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.workdir = tempfile.mkdtemp()
        self.outdir = self.workdir + '/output'
        self.unique_path_mock = mock.patch('koji_cli.commands.unique_path').start()
        self.running_in_bg = mock.patch('koji_cli.commands._running_in_bg').start()
        self.running_in_bg.return_value = False
        self.linked_upload = mock.patch('koji_cli.commands.linked_upload').start()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s import-cg [options] <metadata_file> <files_dir>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.workdir)

    def make_metadata(self, metadata=None, defaults=True, write_outputs=True):
        """Fill in metadata and write to workdir"""
        if metadata is None:
            metadata = {}

        if defaults:
            build = metadata.setdefault('build', {})
            build.setdefault('name', 'mypackage')
            build.setdefault('version', '1')
            build.setdefault('release', '2')

            if 'output' not in metadata:
                metadata['output'] = [
                    {'relpath': 'relative/path', 'filename': 'file-1'},
                    {'relpath': 'relative/path', 'filename': 'file-2'},
                ]

        # write metdata
        fn = os.path.join(self.workdir, 'metadata.json')
        with open(fn, 'wt') as fd:
            json.dump(metadata, fd, indent=4)

        if write_outputs:
            self.write_outputs(metadata)

        return metadata, fn

    def write_outputs(self, metadata):
        # write outputs
        for info in metadata.get('output', []):
            fdir = os.path.join(self.outdir, info.get('relpath', ''))
            koji.ensuredir(fdir)
            fn = os.path.join(fdir, info['filename'])
            with open(fn, 'wt') as fd:
                fd.write('fnord\n')

    def test_handle_import_cg(self):
        """Test handle_import_cg function"""

        metadata, fn = self.make_metadata()
        arguments = [fn, self.outdir]

        # Case 1, running in fg, progress on
        handle_import_cg(self.options, self.session, arguments)

        self.assertEqual(len(self.session.uploadWrapper.mock_calls), len(metadata['output']))
        kwargs = self.session.uploadWrapper.call_args.kwargs
        self.assertEqual(kwargs['callback'], _progress_callback)
        self.session.CGImport.assert_called_once()
        args = self.session.CGImport.call_args.args
        self.assertEqual(args[0], metadata)
        self.linked_upload.assert_not_called()

    def test_handle_import_cg_nodir(self):
        """Test handle_import_cg function"""

        metadata, fn = self.make_metadata(write_outputs=False)
        arguments = [fn]

        self.assert_system_exit(
            handle_import_cg,
            self.options, self.session, arguments,
            stderr=self.format_error_message('Please specify metadata files directory'),
            stdout='',
            activate_session=None
        )

        self.session.uploadWrapper.assert_not_called()
        self.session.CGImport.assert_not_called()
        self.linked_upload.assert_not_called()

    def test_handle_import_cg_output(self):
        """Test handle_import_cg function"""

        metadata, fn = self.make_metadata({}, defaults=False)
        arguments = [fn, self.outdir]

        self.assert_system_exit(
            handle_import_cg,
            self.options, self.session, arguments,
            stderr='Metadata contains no output\n',
            stdout='',
            activate_session=None,
            exit_code=1
        )

        self.session.uploadWrapper.assert_not_called()
        self.session.CGImport.assert_not_called()
        self.linked_upload.assert_not_called()

    def test_handle_import_cg_nofiles(self):
        """Test handle_import_cg function"""

        metadata, fn = self.make_metadata(write_outputs=False)
        arguments = [fn, self.outdir]

        expect = "No such file: %s" % os.path.join(self.outdir, 'relative/path/file-1')
        self.assert_system_exit(
            handle_import_cg,
            self.options, self.session, arguments,
            stderr=self.format_error_message(expect),
            stdout='',
            activate_session=None,
            exit_code=2
        )

        self.session.uploadWrapper.assert_not_called()
        self.linked_upload.assert_not_called()
        self.session.CGImport.assert_not_called()

    def test_handle_import_cg_test(self):
        """Test handle_import_cg function"""

        metadata, fn = self.make_metadata()
        arguments = [fn, self.outdir, '--test']

        handle_import_cg(self.options, self.session, arguments)

        self.session.uploadWrapper.assert_not_called()
        self.linked_upload.assert_not_called()
        self.session.CGImport.assert_not_called()

    def test_handle_import_cg_metaonly(self):
        """Test handle_import_cg function"""

        metadata, fn = self.make_metadata(write_outputs=False)
        for info in metadata['output']:
            info['metadata_only'] = True
        metadata, fn = self.make_metadata(metadata, defaults=False, write_outputs=False)
        arguments = [fn, self.outdir]

        handle_import_cg(self.options, self.session, arguments)

        self.session.uploadWrapper.assert_not_called()
        self.linked_upload.assert_not_called()
        self.session.CGImport.assert_called_once()
        args = self.session.CGImport.call_args.args
        self.assertEqual(args[0], metadata)

    def test_handle_import_cg_draft(self):
        """Test handle_import_cg function"""

        metadata, fn = self.make_metadata()
        arguments = [fn, self.outdir, '--draft']
        # metadata from the call should have draft flag added
        expect = metadata.copy()
        expect['build']['draft'] = True

        # Case 1, running in fg, progress on
        handle_import_cg(self.options, self.session, arguments)

        self.assertEqual(len(self.session.uploadWrapper.mock_calls), len(metadata['output']))
        self.session.CGImport.assert_called_once()
        args = self.session.CGImport.call_args.args
        self.assertEqual(args[0], metadata)

    def test_handle_import_cg_reserve(self):
        """Test handle_import_cg function"""

        metadata, fn = self.make_metadata()
        arguments = [fn, self.outdir, '--build-id', '12345']
        # metadata from the call should have draft flag added
        expect = metadata.copy()
        expect['build']['build_id'] = 12345

        # Case 1, running in fg, progress on
        handle_import_cg(self.options, self.session, arguments)

        self.assertEqual(len(self.session.uploadWrapper.mock_calls), len(metadata['output']))
        self.session.CGImport.assert_called_once()
        args = self.session.CGImport.call_args.args
        self.assertEqual(args[0], expect)

    def test_handle_import_cg_linked(self):
        """Test handle_import_cg function"""

        metadata, fn = self.make_metadata()
        arguments = [fn, self.outdir, '--link']

        handle_import_cg(self.options, self.session, arguments)

        self.session.uploadWrapper.assert_not_called()
        self.assertEqual(len(self.linked_upload.mock_calls), len(metadata['output']))
        self.session.CGImport.assert_called_once()
        args = self.session.CGImport.call_args.args
        self.assertEqual(args[0], metadata)

    def test_handle_import_cg_noprogress(self):
        """Test handle_import_cg function"""

        metadata, fn = self.make_metadata()
        arguments = [fn, self.outdir, '--noprogress']

        handle_import_cg(self.options, self.session, arguments)

        self.assertEqual(len(self.session.uploadWrapper.mock_calls), len(metadata['output']))
        kwargs = self.session.uploadWrapper.call_args.kwargs
        self.assertEqual(kwargs['callback'], None)
        self.session.CGImport.assert_called_once()
        args = self.session.CGImport.call_args.args
        self.assertEqual(args[0], metadata)
        self.linked_upload.assert_not_called()

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


# the end
