from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_import_archive
from . import utils


class TestImportArchive(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_import_archive_without_option(self, stderr):
        expected = "Usage: %s import-archive <build-id|n-v-r> <archive_path> [<archive_path2 ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: You must specify a build ID or N-V-R and " \
                   "an archive to import\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_import_archive(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_import_archive_wrong_type(self, stderr):
        archive_type = 'test-type'
        archive_path = '/mnt/brew/work/test-archive.type'
        expected = "Usage: %s import-archive <build-id|n-v-r> <archive_path> [<archive_path2 ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Unsupported archive type: %s\n" % (self.progname, self.progname,
                                                                  archive_type)
        with self.assertRaises(SystemExit) as ex:
            handle_import_archive(self.options, self.session, ['--type', archive_type, '12',
                                                               archive_path])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
