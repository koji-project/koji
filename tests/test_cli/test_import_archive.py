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
        self.build_id = '1'
        self.archive_path = '/mnt/brew/work/test-archive.type'
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s import-archive <build-id|n-v-r> <archive_path> [<archive_path2 ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_import_archive_without_option(self, stderr):
        expected = self.format_error_message(
            "You must specify a build ID or N-V-R and an archive to import")
        with self.assertRaises(SystemExit) as ex:
            handle_import_archive(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.activate_session_mock.assert_not_called()

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_import_archive_wrong_type(self, stderr):
        archive_type = 'test-type'
        expected = self.format_error_message("Unsupported archive type: %s" % archive_type)
        with self.assertRaises(SystemExit) as ex:
            handle_import_archive(self.options, self.session, ['--type', archive_type,
                                                               self.build_id, self.archive_path])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.activate_session_mock.assert_called_with(self.session, self.options)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_import_archive_without_type(self, stderr):
        expected = self.format_error_message("You must specify an archive type")
        with self.assertRaises(SystemExit) as ex:
            handle_import_archive(self.options, self.session, [self.build_id, self.archive_path])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.activate_session_mock.assert_called_with(self.session, self.options)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_import_archive_type_maven_without_perm(self, stderr):
        archive_type = 'maven'
        self.session.hasPerm.side_effect = [False, False]
        expected = self.format_error_message("This action requires the maven-import privilege")
        with self.assertRaises(SystemExit) as ex:
            handle_import_archive(self.options, self.session,
                                  ['--type', archive_type, self.build_id, self.archive_path])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.activate_session_mock.assert_called_with(self.session, self.options)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_import_archive_type_maven_without_type_info(self, stderr):
        archive_type = 'maven'
        self.session.hasPerm.side_effect = [False, True]
        expected = self.format_error_message(
            "--type-info must point to a .pom file when importing Maven archives")
        with self.assertRaises(SystemExit) as ex:
            handle_import_archive(self.options, self.session,
                                  ['--type', archive_type, self.build_id, self.archive_path])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.activate_session_mock.assert_called_with(self.session, self.options)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_import_archive_type_win_without_perm(self, stderr):
        archive_type = 'win'
        self.session.hasPerm.side_effect = [False, False]
        expected = self.format_error_message("This action requires the win-import privilege")
        with self.assertRaises(SystemExit) as ex:
            handle_import_archive(self.options, self.session,
                                  ['--type', archive_type, self.build_id, self.archive_path])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.activate_session_mock.assert_called_with(self.session, self.options)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_import_archive_type_win_without_type_info(self, stderr):
        archive_type = 'win'
        self.session.hasPerm.side_effect = [False, True]
        expected = self.format_error_message("--type-info must be specified")
        with self.assertRaises(SystemExit) as ex:
            handle_import_archive(self.options, self.session,
                                  ['--type', archive_type, self.build_id, self.archive_path])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.activate_session_mock.assert_called_with(self.session, self.options)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_import_archive_type_win_wrong_type_info(self, stderr):
        archive_type = 'win'
        type_info = 'archive-type'
        self.session.hasPerm.side_effect = [False, True]
        expected = self.format_error_message(
            "--type-info must be in relpath:platforms[:flags] format")
        with self.assertRaises(SystemExit) as ex:
            handle_import_archive(self.options, self.session,
                                  ['--type', archive_type, '--type-info', type_info,
                                   self.build_id, self.archive_path])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.activate_session_mock.assert_called_with(self.session, self.options)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_import_archive_type_image_without_perm(self, stderr):
        archive_type = 'image'
        self.session.hasPerm.side_effect = [False, False]
        expected = self.format_error_message("This action requires the image-import privilege")
        with self.assertRaises(SystemExit) as ex:
            handle_import_archive(self.options, self.session,
                                  ['--type', archive_type, self.build_id, self.archive_path])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.activate_session_mock.assert_called_with(self.session, self.options)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_import_archive_type_image_without_type_info(self, stderr):
        archive_type = 'image'
        self.session.hasPerm.side_effect = [False, True]
        expected = self.format_error_message("--type-info must be specified")
        with self.assertRaises(SystemExit) as ex:
            handle_import_archive(self.options, self.session,
                                  ['--type', archive_type, self.build_id, self.archive_path])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.activate_session_mock.assert_called_with(self.session, self.options)
