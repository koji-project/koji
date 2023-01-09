from __future__ import absolute_import

import mock

import koji
from koji_cli.commands import handle_import_archive
from . import utils


class TestImportArchive(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
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

    def test_import_archive_without_option(self):
        expected = self.format_error_message(
            "You must specify a build ID or N-V-R and an archive to import")
        self.assert_system_exit(
            handle_import_archive,
            self.options, self.session, [],
            stdout='',
            stderr=expected,
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.session.hasPerm.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.createMavenBuild.assert_not_called()
        self.session.createWinBuild.assert_not_called()
        self.session.createImageBuild.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.importArchive.assert_not_called()

    def test_import_archive_wrong_type(self):
        archive_type = 'test-type'
        expected = self.format_error_message("Unsupported archive type: %s" % archive_type)
        self.assert_system_exit(
            handle_import_archive,
            self.options, self.session, ['--type', archive_type, self.build_id, self.archive_path],
            stdout='',
            stderr=expected,
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.hasPerm.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.createMavenBuild.assert_not_called()
        self.session.createWinBuild.assert_not_called()
        self.session.createImageBuild.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.importArchive.assert_not_called()

    def test_import_archive_without_type(self):
        self.assert_system_exit(
            handle_import_archive,
            self.options, self.session, [self.build_id, self.archive_path],
            stdout='',
            stderr=self.format_error_message("You must specify an archive type"),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.hasPerm.assert_not_called()
        self.session.getBuild.assert_not_called()
        self.session.createMavenBuild.assert_not_called()
        self.session.createWinBuild.assert_not_called()
        self.session.createImageBuild.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.importArchive.assert_not_called()

    def test_import_archive_type_maven_without_perm(self):
        archive_type = 'maven'
        self.session.hasPerm.side_effect = [False, False]
        self.assert_system_exit(
            handle_import_archive,
            self.options, self.session, ['--type', archive_type, self.build_id, self.archive_path],
            stdout='',
            stderr=self.format_error_message("This action requires the maven-import privilege"),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.hasPerm.assert_has_calls([mock.call('maven-import'), mock.call('admin')])
        self.session.getBuild.assert_not_called()
        self.session.createMavenBuild.assert_not_called()
        self.session.createWinBuild.assert_not_called()
        self.session.createImageBuild.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.importArchive.assert_not_called()

    def test_import_archive_type_maven_without_type_info(self):
        archive_type = 'maven'
        self.session.hasPerm.side_effect = [False, True]
        expected = self.format_error_message(
            "--type-info must point to a .pom file when importing Maven archives")
        self.assert_system_exit(
            handle_import_archive,
            self.options, self.session, ['--type', archive_type, self.build_id, self.archive_path],
            stdout='',
            stderr=expected,
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.hasPerm.assert_has_calls([mock.call('maven-import'), mock.call('admin')])
        self.session.getBuild.assert_not_called()
        self.session.createMavenBuild.assert_not_called()
        self.session.createWinBuild.assert_not_called()
        self.session.createImageBuild.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.importArchive.assert_not_called()

    def test_import_archive_type_win_without_perm(self):
        archive_type = 'win'
        self.session.hasPerm.side_effect = [False, False]
        self.assert_system_exit(
            handle_import_archive,
            self.options, self.session, ['--type', archive_type, self.build_id, self.archive_path],
            stdout='',
            stderr=self.format_error_message("This action requires the win-import privilege"),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.hasPerm.assert_has_calls([mock.call('win-import'), mock.call('admin')])
        self.session.getBuild.assert_not_called()
        self.session.createMavenBuild.assert_not_called()
        self.session.createWinBuild.assert_not_called()
        self.session.createImageBuild.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.importArchive.assert_not_called()

    def test_import_archive_type_win_without_type_info(self):
        archive_type = 'win'
        self.session.hasPerm.side_effect = [False, True]
        self.assert_system_exit(
            handle_import_archive,
            self.options, self.session, ['--type', archive_type, self.build_id, self.archive_path],
            stdout='',
            stderr=self.format_error_message("--type-info must be specified"),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.hasPerm.assert_has_calls([mock.call('win-import'), mock.call('admin')])
        self.session.getBuild.assert_not_called()
        self.session.createMavenBuild.assert_not_called()
        self.session.createWinBuild.assert_not_called()
        self.session.createImageBuild.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.importArchive.assert_not_called()

    def test_import_archive_type_win_wrong_type_info(self):
        archive_type = 'win'
        type_info = 'archive-type'
        self.session.hasPerm.side_effect = [False, True]
        expected = self.format_error_message(
            "--type-info must be in relpath:platforms[:flags] format")
        self.assert_system_exit(
            handle_import_archive,
            self.options, self.session,
            ['--type', archive_type, '--type-info', type_info, self.build_id, self.archive_path],
            stdout='',
            stderr=expected,
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.hasPerm.assert_has_calls([mock.call('win-import'), mock.call('admin')])
        self.session.getBuild.assert_not_called()
        self.session.createMavenBuild.assert_not_called()
        self.session.createWinBuild.assert_not_called()
        self.session.createImageBuild.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.importArchive.assert_not_called()

    def test_import_archive_type_image_without_perm(self):
        archive_type = 'image'
        self.session.hasPerm.side_effect = [False, False]
        self.assert_system_exit(
            handle_import_archive,
            self.options, self.session, ['--type', archive_type, self.build_id, self.archive_path],
            stdout='',
            stderr=self.format_error_message("This action requires the image-import privilege"),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.hasPerm.assert_has_calls([mock.call('image-import'), mock.call('admin')])
        self.session.getBuild.assert_not_called()
        self.session.createMavenBuild.assert_not_called()
        self.session.createWinBuild.assert_not_called()
        self.session.createImageBuild.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.importArchive.assert_not_called()

    def test_import_archive_type_image_without_type_info(self):
        archive_type = 'image'
        self.session.hasPerm.side_effect = [False, True]
        self.assert_system_exit(
            handle_import_archive,
            self.options, self.session, ['--type', archive_type, self.build_id, self.archive_path],
            stdout='',
            stderr=self.format_error_message("--type-info must be specified"),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_with(self.session, self.options)
        self.session.hasPerm.assert_has_calls([mock.call('image-import'), mock.call('admin')])
        self.session.getBuild.assert_not_called()
        self.session.createMavenBuild.assert_not_called()
        self.session.createWinBuild.assert_not_called()
        self.session.createImageBuild.assert_not_called()
        self.session.uploadWrapper.assert_not_called()
        self.session.importArchive.assert_not_called()

    def test_import_archive_help(self):
        self.assert_help(
            handle_import_archive,
            """Usage: %s import-archive <build-id|n-v-r> <archive_path> [<archive_path2 ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --noprogress          Do not display progress of the upload
  --create-build        Auto-create builds as needed
  --link                Attempt to hardlink instead of uploading
  --type=TYPE           The type of archive being imported. Currently
                        supported types: maven, win, image
  --type-info=TYPE_INFO
                        Type-specific information to associate with the
                        archives. For Maven archives this should be a local
                        path to a .pom file. For Windows archives this should
                        be relpath:platforms[:flags])) Images need an arch
""" % self.progname)
