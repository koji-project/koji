from __future__ import absolute_import
from __future__ import print_function
import copy
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import anon_handle_wait_repo
from . import utils


class TestWaitRepo(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None
    longMessage = True

    TAG = {
        'maven_support': False,
        'locked': False,
        'name': 'fedora26-build',
        'extra': {},
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
        self.options.poll_interval = 1  # second
        self.options.weburl = 'https://localhost.local'

        self.session = mock.MagicMock()
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
        self.checkForBuilds = mock.patch('koji.util.checkForBuilds').start()

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('time.time')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    def __test_wait_repo(self, args, expected, stderr, stdout, time_mock, ret_code=0):
        self.options.quiet = False
        time_mock.side_effect = [0, 1, 2, 3]
        if ret_code:
            with self.assertRaises(SystemExit) as ex:
                anon_handle_wait_repo(self.options, self.session, args)
            self.assertExitCode(ex, ret_code)
            self.assert_console_message(stderr, expected)
            self.assert_console_message(stdout, '')
        else:
            rv = anon_handle_wait_repo(self.options, self.session, args)
            self.assert_console_message(stdout, expected)
            self.assert_console_message(stderr, '')
            self.assertIn(rv, [0, None])

    @mock.patch('time.time')
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    def __test_wait_repo_timeout(self, args, expected, stderr, stdout, time_mock, ret_code=0):
        self.options.quiet = False
        time_mock.side_effect = [0, 61, 62]
        if ret_code:
            with self.assertRaises(SystemExit) as ex:
                anon_handle_wait_repo(self.options, self.session, args + ['--timeout', '1'])
            self.assertExitCode(ex, ret_code)
            self.assert_console_message(stderr, expected)
            self.assert_console_message(stdout, '')
        else:
            rv = anon_handle_wait_repo(self.options, self.session, args + ['--timeout', '1'])
            self.assert_console_message(stdout, expected)
            self.assert_console_message(stderr, '')
            self.assertIn(rv, [0, None])

    def test_anon_handle_wait_repo(self):
        """Test anon_handle_wait_repo function"""
        arguments = [self.tag_name]

        self.options.quiet = False
        self.session.getRepo.side_effect = [{}, {}, {'id': 1, 'name': 'DEFAULT'}]
        expected = 'Successfully waited 0:03 for a new %s repo' % self.tag_name + '\n'
        self.__test_wait_repo(arguments, expected)

    def test_anon_handle_wait_repo_with_target_opt(self):
        """Test anon_handle_wait_repo function with --target option"""
        arguments = [self.tag_name, '--target']

        self.options.quiet = False
        self.session.getBuildTarget.return_value = {'build_tag_name': self.tag_name, 'build_tag': 1}
        self.session.getRepo.side_effect = [{}, {}, {'id': 1, 'name': 'DEFAULT'}]
        expected = 'Successfully waited 0:03 for a new %s repo' % self.tag_name + '\n'
        self.__test_wait_repo(arguments, expected)

    def test_anon_handle_wait_repo_timeout(self):
        """Test anon_handle_wait_repo function on timeout case"""
        arguments = [self.tag_name]

        self.options.quiet = False
        self.session.getRepo.return_value = {}
        self.checkForBuilds.return_value = True
        expected = 'Unsuccessfully waited 1:02 for a new %s repo' % self.tag_name + '\n'
        self.__test_wait_repo_timeout(arguments, expected, ret_code=1)

    def test_anon_handle_wait_repo_with_build(self):
        """Test anon_handle_wait_repo function with --build options"""
        builds = ['bash-4.4.12-5.fc26', 'sed-4.4-1.fc26']
        new_ver = 'bash-4.4.12-7.fc26'
        arguments = [self.tag_name]
        pkgs = ''
        for b in builds:
            arguments += ['--build', b]
            pkgs += b + ':'
        pkgs = pkgs[:-1].replace(':', ' and ')

        self.options.quiet = False
        self.session.getLatestBuilds.side_effect = [
            [{'nvr': new_ver}], []
        ]
        self.checkForBuilds.return_value = True
        self.session.getRepo.side_effect = [
            {}, {}, {'id': 1, 'name': 'DEFAULT', 'create_event': 1}
        ]
        expected = 'Warning: nvr %s is not current in tag %s\n  latest build in %s is %s' % \
                   (builds[0], self.tag_name, self.tag_name, new_ver) + "\n"
        expected += 'Warning: package sed is not in tag %s' % self.tag_name + '\n'
        expected += 'Successfully waited 0:03 for %s to appear in the %s repo' % (pkgs, self.tag_name) + '\n'
        self.__test_wait_repo(arguments, expected)

    def test_anon_handle_wait_repo_with_build_timeout(self):
        """Test anon_handle_wait_repo function with --build options on timeout cases"""
        builds = ['bash-4.4.12-5.fc26', 'sed-4.4-1.fc26']
        arguments = [self.tag_name]
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
        self.checkForBuilds.return_value = True
        self.session.getRepo.return_value = {}
        expected = 'Unsuccessfully waited 1:02 for %s to appear in the %s repo' % (pkgs, self.tag_name) + '\n'
        self.__test_wait_repo_timeout(arguments, expected, ret_code=1)

    def test_anon_handle_wait_repo_errors(self):
        """Test anon_handle_wait_repo function errors and exceptions"""
        tests = [
            # [ arguments, error_string ]
            [[], "Please specify a tag name"],
            [['tag1', 'tag2'], "Only one tag may be specified"],
            [[self.tag_name], "Invalid tag: %s" % self.tag_name],
            [[self.tag_name, '--target'], "Invalid build target: %s" % self.tag_name],
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

        # Case 1. both build and dest targets are not found
        self.session.getTag.return_value = self.TAG.copy()
        self.session.getBuildTargets.return_value = []
        with self.assertRaises(SystemExit) as ex:
            anon_handle_wait_repo(self.options, self.session, [self.tag_name])
        self.assertExitCode(ex, 1)
        expected = "%(name)s is not a build tag for any target" % self.TAG + "\n"
        self.assert_console_message(stderr, expected)

        # Cas 2. dest is matched, show suggestion
        self.session.getBuildTargets.side_effect = [
            [],
            [
                {'build_tag_name': 'build-tag-1'},
                {'build_tag_name': 'build-tag-2'},
                {'build_tag_name': 'build-tag-3'},
            ],
        ]
        with self.assertRaises(SystemExit) as ex:
            anon_handle_wait_repo(self.options, self.session, [self.tag_name])
        self.assertExitCode(ex, 1)
        expected = "%(name)s is not a build tag for any target" % self.TAG + "\n"
        expected += "Suggested tags: build-tag-1, build-tag-2, build-tag-3\n"
        self.assert_console_message(stderr, expected)

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
  --timeout=TIMEOUT  Amount of time to wait (in minutes) before giving up
                     (default: 120)
  --quiet            Suppress output, success or failure will be indicated by
                     the return value only
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
