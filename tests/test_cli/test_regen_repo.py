from __future__ import absolute_import
from __future__ import print_function
import copy
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_regen_repo
from . import utils


class TestRegenRepo(utils.CliTestCase):

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
        self.options.poll_interval = 100
        self.options.weburl = 'https://localhost.local'

        self.session = mock.MagicMock()
        self.session.getTag.return_value = copy.deepcopy(self.TAG)
        self.session.newRepo.return_value = self.task_id
        self.session.getBuildTarget.return_value = {'build_tag_name': self.tag_name}

        self.error_format = """Usage: %s regen-repo [options] <tag>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

        self.setUpMocks()

    def setUpMocks(self):
        self.activate_session = mock.patch('koji_cli.commands.activate_session').start()

        self.running_in_bg = mock.patch('koji_cli.commands._running_in_bg').start()
        self.running_in_bg.return_value = False     # assume run in foreground

        self.watch_tasks = mock.patch('koji_cli.commands.watch_tasks').start()
        self.watch_tasks.return_value = True

        self.mocks_table = {}
        for m in ('activate_session', 'running_in_bg', 'watch_tasks'):
            self.mocks_table[m] = getattr(self, m)
            self.addCleanup(self.mocks_table[m].stop)

    def resetMocks(self):
        for m in self.mocks_table.values():
            m.reset()

    def tearDown(self):
        mock.patch.stopall()

    def __run_test_handle_regen_repo(self, arguments, return_value=None, expected=''):
        expected += "Regenerating repo for tag: %s" % self.tag_name + "\n"
        expected += "Created task: %d" % self.task_id + "\n"
        expected += "Task info: %s/taskinfo?taskID=%s" % (self.options.weburl, self.task_id) + "\n"
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            rv = handle_regen_repo(self.options, self.session, arguments)
            self.assertEqual(rv, return_value)
        self.assert_console_message(stdout, expected)
        self.activate_session.assert_called_with(self.session, self.options)

    def test_handle_regen_repo(self):
        """Test handle_regen_repo function"""

        # show error if tag is not exist
        self.session.getTag.return_value = {}
        expected = self.format_error_message("No matching tag: " + self.tag_name)
        self.assert_system_exit(
            handle_regen_repo,
            self.options,
            self.session,
            [self.tag_name],
            stderr=expected)

        self.resetMocks()

        # show warning if tag is not a build tag
        self.session.getTag.return_value = copy.copy(self.TAG)
        self.session.getBuildTargets.return_value = []
        expected = "Warning: %s is not a build tag" % self.tag_name + "\n"
        self.__run_test_handle_regen_repo([self.tag_name], True, expected=expected)

        self.resetMocks()
        # show warning message if arch is empty
        noarch_tag = copy.copy(self.TAG)
        noarch_tag.update({'arches': ''})
        self.session.getTag.return_value = noarch_tag
        expected += "Warning: tag %s has an empty arch list" % noarch_tag['name'] + "\n"
        self.__run_test_handle_regen_repo([self.tag_name], True, expected=expected)

    def test_handle_regen_repo_with_target_opt(self):
        """Test handle_regen_repo function with --target option"""
        arguments = [self.tag_name, '--target']

        # show error if target is not matched
        self.session.getBuildTarget.return_value = {}
        expected = self.format_error_message("No matching build target: " + self.tag_name)
        self.assert_system_exit(
            handle_regen_repo,
            self.options,
            self.session,
            arguments,
            stderr=expected)

        self.resetMocks()

        self.session.getBuildTarget.return_value = {'build_tag_name': self.tag_name}
        self.__run_test_handle_regen_repo(arguments, True)

    def test_handle_regen_repo_with_other_opts(self):
        """Test handle_regen_repo function with options"""
        # --nowait
        self.__run_test_handle_regen_repo([self.tag_name, '--nowait'], None)
        self.resetMocks()

        # --source && --debuginfo
        self.__run_test_handle_regen_repo([self.tag_name, '--source', '--debuginfo'], True)
        self.session.newRepo.assert_called_with(self.tag_name, **{'debuginfo': True, 'src': True})

    def test_handle_regen_repo_errors(self):
        """Test handle_regen_repo function errors and exceptions"""
        tests = [
            # [ arguments, error_string ]
            [[], self.format_error_message("A tag name must be specified")],
            [['tag1', 'tag2'], self.format_error_message("Only a single tag name may be specified")],
            [['tag1', 'tag2', '--target'], self.format_error_message("Only a single target may be specified")],
        ]

        for test in tests:
            self.assert_system_exit(
                handle_regen_repo,
                self.options,
                self.session,
                test[0],
                stderr=test[1],
                activate_session=None)
        self.activate_session.assert_not_called()

    def test_handle_regen_repo_help(self):
        """Test handle_regen_repo help message"""
        self.assert_help(
            handle_regen_repo,
            """Usage: %s regen-repo [options] <tag>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --target              Interpret the argument as a build target name
  --nowait              Don't wait on for regen to finish
  --debuginfo           Include debuginfo rpms in repo
  --source, --src       Include source rpms in each of repos
  --separate-source, --separate-src
                        Include source rpms in separate src repo
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
