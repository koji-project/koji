from __future__ import absolute_import

import mock
import six

from koji_cli.commands import handle_add_external_repo
from . import utils


class TestAddExternalRepo(utils.CliTestCase):

    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s add-external-repo [options] <name> [<url>]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.name = 'test-repo'
        self.url = 'https://path/to/ext/repo'
        self.rinfo = {'id': 1, 'name': self.name, 'url': self.url}
        self.tag = 'test-tag'
        self.priority = 10

    def tearDown(self):
        mock.patch.stopall()

    def test_add_external_repo_invalid_mode(self):
        mode = 'test-mode'
        arguments = ['--mode', mode]
        self.assert_system_exit(
            handle_add_external_repo,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message('Invalid mode: %s' % mode),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_add_external_repo_mode_without_tag(self):
        arguments = ['--mode', 'koji']
        self.assert_system_exit(
            handle_add_external_repo,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message('The --mode option can only be used with --tag'),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_add_external_repo_one_arg_without_tag(self):
        repo_info = [
            {'id': 1,
             'name': 'test-ext-repo',
             'url': 'https://path/to/ext/repo'},
        ]
        name = 'test-ext-repo'
        self.session.getExternalRepo.return_value = repo_info
        arguments = [name]
        self.assert_system_exit(
            handle_add_external_repo,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message('A url is required to create an external repo entry'),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getExternalRepo.assert_called_once_with(name, strict=True)

    def test_add_external_repo_incorect_num_of_args(self):
        arguments = []
        self.assert_system_exit(
            handle_add_external_repo,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message('Incorrect number of arguments'),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_add_external_repo_valid(self, stdout):
        self.session.createExternalRepo.return_value = self.rinfo
        self.session.addExternalRepoToTag.return_value = None

        handle_add_external_repo(self.options, self.session,
                                 [self.name, self.url, '--tag',
                                  '%s::%s' % (self.tag, str(self.priority))])
        actual = stdout.getvalue()
        expected = 'Created external repo %i\nAdded external repo %s to tag %s (priority %i)\n' \
                   % (self.rinfo['id'], self.rinfo['name'], self.tag, self.priority)
        self.assertMultiLineEqual(actual, expected)

        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.createExternalRepo.assert_called_once_with(self.name, self.url)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_add_external_repo_without_priority(self, stdout):
        self.session.createExternalRepo.return_value = self.rinfo
        self.session.addExternalRepoToTag.return_value = None
        self.session.getTagExternalRepos.return_value = None

        handle_add_external_repo(self.options, self.session,
                                 [self.name, self.url, '--tag', self.tag, '--mode=koji',
                                  '--arches=arch'])
        actual = stdout.getvalue()
        expected = 'Created external repo %i\nAdded external repo %s to tag %s (priority 5)\n' \
                   % (self.rinfo['id'], self.rinfo['name'], self.tag)
        self.assertMultiLineEqual(actual, expected)

        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.createExternalRepo.assert_called_once_with(self.name, self.url)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_add_external_repo_with_option_priority(self, stdout):
        self.session.createExternalRepo.return_value = self.rinfo
        self.session.addExternalRepoToTag.return_value = None
        self.session.getTagExternalRepos.return_value = None
        priority = 3

        handle_add_external_repo(self.options, self.session,
                                 [self.name, self.url, '--tag', self.tag, '--mode=koji',
                                  '--arches=arch', '--priority', str(priority)])
        actual = stdout.getvalue()
        expected = 'Created external repo %i\nAdded external repo %s to tag %s (priority %i)\n' \
                   % (self.rinfo['id'], self.rinfo['name'], self.tag, priority)
        self.assertMultiLineEqual(actual, expected)

        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.createExternalRepo.assert_called_once_with(self.name, self.url)

    def test_handle_add_external_repo_help(self):
        self.assert_help(
            handle_add_external_repo,
            """Usage: %s add-external-repo [options] <name> [<url>]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  -t TAG, --tag=TAG     Also add repo to tag. Use tag::N to set priority
  -p PRIORITY, --priority=PRIORITY
                        Set priority (when adding to tag)
  -m MODE, --mode=MODE  Set merge mode
  -a ARCH1,ARCH2, ..., --arches=ARCH1,ARCH2, ...
                        Use only subset of arches from given repo
""" % self.progname)
