from __future__ import absolute_import
from __future__ import absolute_import
from __future__ import print_function

import unittest
import copy

try:
    from unittest import mock
except ImportError:
    import mock
import pytest
import six

import koji
from koji_cli.commands import anon_handle_wait_repo
from . import utils

class TestWaitRepo(utils.CliTestCase):

    """
    These older tests cover the non-request code path for the cli handler
    """

    # Show long diffs in error output...
    maxDiff = None
    longMessage = True

    TAG = {
        'maven_support': False,
        'locked': False,
        'name': 'fedora26-build',
        'extra': {'repo.auto': True},
        'perm': None,
        'id': 2,
        'arches': 'x86_64',
        'maven_include_all': False,
        'perm_id': None
    }

    def setUp(self):
        self.task_id = 1001
        self.tag_name = self.TAG['name']

        self.options = mock.MagicMock()
        self.options.quiet = True
        self.options.poll_interval = 0.0001  # keep it fast
        self.options.weburl = 'https://localhost.local'

        self.session = mock.MagicMock()
        self.session.hub_version = (1, 35, 0)
        self.session.getTag.return_value = copy.deepcopy(self.TAG)
        self.session.newRepo.return_value = self.task_id
        self.session.getBuildTarget.return_value = {'build_tag_name': self.tag_name}

        self.error_format = """Usage: %s wait-repo [options] <tag>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

        self.setUpMocks()

    def setUpMocks(self):
        self.activate_session = mock.patch('koji_cli.commands.activate_session').start()
        self.ensure_connection = mock.patch('koji_cli.commands.ensure_connection').start()
        self.watcher = mock.MagicMock()
        self.RepoWatcher = mock.patch('koji.util.RepoWatcher', return_value=self.watcher).start()
        self.wait_logger = mock.MagicMock()
        self.getLogger = mock.patch('logging.getLogger', return_value=self.wait_logger).start()

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    def __test_wait_repo(self, args, expected, stderr, stdout, ret_code=0,
                         expected_warn=''):
        self.options.quiet = False
        if ret_code:
            with self.assertRaises(SystemExit) as ex:
                anon_handle_wait_repo(self.options, self.session, args)
            self.assertExitCode(ex, ret_code)
            self.assert_console_message(stderr, expected)
            self.assert_console_message(stdout, '')
        else:
            rv = anon_handle_wait_repo(self.options, self.session, args)
            self.assert_console_message(stdout, expected)
            self.assert_console_message(stderr, expected_warn)
            self.assertIn(rv, [0, None])

    def test_anon_handle_wait_repo(self):
        """Test anon_handle_wait_repo function"""
        arguments = [self.tag_name, '--no-request']

        self.options.quiet = False
        self.watcher.waitrepo.return_value = {'id': 1, 'name': 'DEFAULT'}
        expected = (
            'Got repo 1\n'
            'Repo info: https://localhost.local/repoinfo?repoID=1\n'
        )
        self.__test_wait_repo(arguments, expected)

    def test_anon_handle_wait_repo_with_target_opt(self):
        """Test anon_handle_wait_repo function with --target option"""
        arguments = [self.tag_name, '--target', '--no-request']

        self.options.quiet = False
        self.session.getBuildTarget.return_value = {'build_tag_name': self.tag_name,
                                                    'build_tag': 1}
        self.watcher.waitrepo.return_value = {'id': 1, 'name': 'DEFAULT'}
        expected = (
            'Got repo 1\n'
            'Repo info: https://localhost.local/repoinfo?repoID=1\n'
        )
        self.__test_wait_repo(arguments, expected)

    def test_anon_handle_wait_repo_timeout(self):
        """Test anon_handle_wait_repo function on timeout case"""
        arguments = [self.tag_name, '--no-request']

        self.options.quiet = False
        self.watcher.waitrepo.side_effect = koji.GenericError('timeout')
        expected = 'Failed to get repo -- timeout\n'
        self.__test_wait_repo(arguments, expected, ret_code=1)

    def test_anon_handle_wait_repo_with_build(self):
        """Test anon_handle_wait_repo function with --build options"""
        builds = ['bash-4.4.12-5.fc26', 'sed-4.4-1.fc26']
        new_ver = 'bash-4.4.12-7.fc26'
        arguments = [self.tag_name, '--no-request']
        pkgs = ''
        for b in builds:
            arguments += ['--build', b]
            pkgs += b + ':'
        pkgs = pkgs[:-1].replace(':', ' and ')

        self.options.quiet = False
        self.session.getLatestBuilds.side_effect = [
            [{'nvr': new_ver}], []
        ]
        self.watcher.waitrepo.return_value = {'id': 1, 'name': 'DEFAULT', 'create_event': 1}

        expected_warn = 'nvr %s is not current in tag %s\n  latest build is %s' % \
                   (builds[0], self.tag_name, new_ver) + "\n"
        expected_warn += 'No sed builds in tag %s' % self.tag_name + '\n'
        expected = (
            'Got repo 1\n'
            'Repo info: https://localhost.local/repoinfo?repoID=1\n'
        )
        self.__test_wait_repo(arguments, expected, expected_warn=expected_warn)
        self.RepoWatcher.assert_called_with(self.session, self.TAG['id'], nvrs=builds, min_event=None, logger=self.wait_logger)

    def test_anon_handle_wait_repo_with_build_timeout(self):
        """Test anon_handle_wait_repo function with --build options on timeout cases"""
        builds = ['bash-4.4.12-5.fc26', 'sed-4.4-1.fc26']
        arguments = [self.tag_name, '--no-request']
        pkgs = ''
        for b in builds:
            arguments += ['--build', b]
            pkgs += b + ':'
        pkgs = pkgs[:-1].replace(':', ' and ')

        self.options.quiet = False
        self.session.getLatestBuilds.side_effect = [
            [{'nvr': builds[0]}],
            [{'nvr': builds[1]}],
        ]
        self.watcher.waitrepo.side_effect = koji.GenericError('timeout')
        expected = 'Failed to get repo -- timeout\n'
        self.__test_wait_repo(arguments, expected, ret_code=1)

    def test_anon_handle_wait_repo_errors(self):
        """Test anon_handle_wait_repo function errors and exceptions"""
        tests = [
            # [ arguments, error_string ]
            [['--no-request'], "Please specify a tag name"],
            [['tag1', 'tag2', '--no-request'], "Only one tag may be specified"],
            [[self.tag_name, '--no-request'], "No such tag: %s" % self.tag_name],
            [[self.tag_name, '--target', '--no-request'], "No such build target: %s" % self.tag_name],
        ]

        self.session.getBuildTarget.return_value = {}
        self.session.getTag.return_value = {}

        for test in tests:
            self.assert_system_exit(
                anon_handle_wait_repo,
                self.options,
                self.session,
                test[0],
                stderr=self.format_error_message(test[1]),
                activate_session=None)
        self.activate_session.assert_not_called()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    def test_anon_handle_wait_repo_target_not_found(self, stderr):
        """Test anon_handle_wait_repo function on target not found cases"""
        # Should warn, but continue to watch

        # Case 1. both build and dest targets are not found
        self.session.getTag.return_value = self.TAG.copy()
        self.session.getBuildTargets.return_value = []

        anon_handle_wait_repo(self.options, self.session, [self.tag_name, '--no-request'])

        expected = "%(name)s is not a build tag for any target" % self.TAG + "\n"
        self.assert_console_message(stderr, expected)
        self.RepoWatcher.assert_called_with(self.session, self.TAG['id'], nvrs=[], min_event=None, logger=self.wait_logger)

        # Cas 2. dest is matched, show suggestion
        self.RepoWatcher.reset_mock()
        self.session.getBuildTargets.side_effect = [
            [],
            [
                {'build_tag_name': 'build-tag-1'},
                {'build_tag_name': 'build-tag-2'},
                {'build_tag_name': 'build-tag-3'},
            ],
        ]
        anon_handle_wait_repo(self.options, self.session, [self.tag_name, '--no-request'])
        expected = "%(name)s is not a build tag for any target" % self.TAG + "\n"
        expected += "Suggested tags: build-tag-1, build-tag-2, build-tag-3\n"
        self.assert_console_message(stderr, expected)
        self.RepoWatcher.assert_called_with(self.session, self.TAG['id'], nvrs=[], min_event=None, logger=self.wait_logger)

    def test_anon_handle_wait_repo_help(self):
        """Test anon_handle_wait_repo help message"""
        self.assert_help(
            anon_handle_wait_repo,
            """Usage: %s wait-repo [options] <tag>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help         show this help message and exit
  --build=NVR        Check that the given build is in the newly-generated repo
                     (may be used multiple times)
  --target           Interpret the argument as a build target name
  --request          Create a repo request (requires auth)
  --no-request       Do not create a repo request (the default)
  --timeout=TIMEOUT  Amount of time to wait (in minutes) before giving up
                     (default: 120)
  -v, --verbose      Be verbose
  --quiet            Suppress output, success or failure will be indicated by
                     the return value only
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
