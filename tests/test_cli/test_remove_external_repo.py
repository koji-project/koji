from __future__ import absolute_import
import mock
from six.moves import StringIO

from koji_cli.commands import handle_remove_external_repo
from . import utils


class TestRemoveExternalRepo(utils.CliTestCase):

    def setUp(self):
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s remove-external-repo <repo> [<tag> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def test_remove_external_repo_help(self):
        self.assert_help(
            handle_remove_external_repo,
            """Usage: %s remove-external-repo <repo> [<tag> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
  --alltags   Remove from all tags
  --force     Force action
""" % self.progname)

    def test_remove_external_repo_without_arg(self):
        arguments = []
        self.assert_system_exit(
            handle_remove_external_repo,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("Incorrect number of arguments"),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()

    def test_remove_external_repo_delete_without_force(self):
        self.session.getTagExternalRepos.return_value = [{'external_repo_id': 11,
                                                          'tag_id': 1,
                                                          'tag_name': 'test-tag',
                                                          'priority': 5,
                                                          'merge_mode': 'simple',
                                                          'arches': 'x86_64 i686'}]
        repo = 'test-repo'
        tag = 'test-tag'
        exp_error = "Error: external repo %s used by tag(s): %s\nUse --force to remove anyway\n" \
                    % (repo, tag)
        arguments = [repo]
        self.assert_system_exit(
            handle_remove_external_repo,
            self.options, self.session, arguments,
            stdout='',
            stderr=exp_error,
            exit_code=1,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_remove_external_repo_delete_valid(self, stdout):
        self.session.getTagExternalRepos.return_value = [{'external_repo_id': 11,
                                                          'tag_id': 1,
                                                          'tag_name': 'test-tag',
                                                          'priority': 5,
                                                          'merge_mode': 'simple',
                                                          'arches': 'x86_64 i686'}]
        repo = 'test-repo'
        handle_remove_external_repo(self.options, self.session, ['--force', repo])
        self.assert_console_message(stdout, '')
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_remove_external_repo_alltags_with_tag(self):
        self.session.getTagExternalRepos.return_value = [{'external_repo_id': 11,
                                                          'tag_id': 1,
                                                          'tag_name': 'test-tag',
                                                          'priority': 5,
                                                          'merge_mode': 'simple',
                                                          'arches': 'x86_64 i686'}]
        repo = 'test-repo'
        tag = 'test-tag'
        arguments = ['--alltags', repo, tag]
        self.assert_system_exit(
            handle_remove_external_repo,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("Do not specify tags when using --alltags"),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_remove_external_repo_alltags_not_associated_without_force(self, stderr):
        self.session.getTagExternalRepos.return_value = []
        repo = 'test-repo'
        handle_remove_external_repo(self.options, self.session, ['--alltags', repo])
        self.assert_console_message(stderr,
                                    'External repo %s not associated with any tags\n' % repo)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_remove_external_repo_remove_not_associated_tag(self, stdout):
        self.session.getTagExternalRepos.return_value = [{'external_repo_id': 11,
                                                          'tag_id': None,
                                                          'tag_name': None,
                                                          'priority': 5,
                                                          'merge_mode': 'simple',
                                                          'arches': 'x86_64 i686'}]
        repo = 'test-repo'
        tag = 'test-tag'
        handle_remove_external_repo(self.options, self.session, [repo, tag])
        self.assert_console_message(
            stdout, 'External repo %s not associated with tag %s\n' % (repo, tag))
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_remove_external_repo_remove_valid(self, stdout):
        self.session.getTagExternalRepos.return_value = [{'external_repo_id': 11,
                                                          'tag_id': 1,
                                                          'tag_name': 'test-tag',
                                                          'priority': 5,
                                                          'merge_mode': 'simple',
                                                          'arches': 'x86_64 i686'}]
        repo = 'test-repo'
        tag = 'test-tag'
        handle_remove_external_repo(self.options, self.session, [repo, tag])
        self.assert_console_message(stdout, '')
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
