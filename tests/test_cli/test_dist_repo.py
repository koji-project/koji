from __future__ import absolute_import
from __future__ import print_function
import copy
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest


from koji_cli.commands import handle_dist_repo
from . import utils


class TestDistRepo(utils.CliTestCase):

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
        self.tag_name = 'tag_name'
        self.fake_key = '11223344'

        self.options = mock.MagicMock()
        self.options.quiet = True
        self.options.poll_interval = 100

        self.session = mock.MagicMock()
        self.session.getTag.return_value = copy.deepcopy(self.TAG)
        self.session.distRepo.return_value = self.task_id

        self.error_format = """Usage: %s dist-repo [options] <tag> <key_id> [<key_id> ...]

In normal mode, dist-repo behaves like any other koji task.
Sometimes you want to limit running distRepo tasks per tag to only
one. For such behaviour admin (with 'tag' permission) needs to
modify given tag's extra field 'distrepo.cancel_others' to True'
via 'koji edit-tag -x distrepo.cancel_others=True'

(Specify the --help option for a list of other options)

%s: error: {message}
""" % (self.progname, self.progname)

        self.setUpMocks()

    def setUpMocks(self):
        self.unique_path = mock.patch('koji_cli.commands.unique_path').start()
        self.unique_path.return_value = '/path/to/cli-dist-repo'
        self.activate_session = mock.patch('koji_cli.commands.activate_session').start()

        self.running_in_bg = mock.patch('koji_cli.commands._running_in_bg').start()
        self.running_in_bg.return_value = False     # assume run in foreground

        self.watch_tasks = mock.patch('koji_cli.commands.watch_tasks').start()
        self.watch_tasks.return_value = True

        self.mocks_table = {}
        for m in ('unique_path', 'activate_session', 'running_in_bg', 'watch_tasks'):
            self.mocks_table[m] = getattr(self, m)
            self.addCleanup(self.mocks_table[m].stop)

    def resetMocks(self):
        for m in self.mocks_table.values():
            m.reset()

    def tearDown(self):
        mock.patch.stopall()

    def __run_test_handle_dist_repo(self, arguments, return_value=None, expected=''):
        expected = expected + "Creating dist repo for tag " + self.tag_name + "\n"
        with mock.patch('sys.stdout', new_callable=six.StringIO) as stdout:
            rv = handle_dist_repo(self.options, self.session, arguments)
            self.assertEqual(rv, return_value)
        self.assert_console_message(stdout, expected)
        self.activate_session.assert_called_with(self.session, self.options)

    def test_handle_dist_repo(self):
        arguments = [self.tag_name, self.fake_key]
        self.__run_test_handle_dist_repo(arguments, True)
        self.watch_tasks.assert_called_with(
                self.session,
                [self.task_id],
                quiet=self.options.quiet,
                poll_interval=self.options.poll_interval)

    def test_handle_dist_repo_nowait(self):
        arguments = [self.tag_name, self.fake_key, '--nowait']
        self.__run_test_handle_dist_repo(arguments, None)
        self.activate_session.assert_called_with(self.session, self.options)
        self.watch_tasks.assert_not_called()

    def test_handle_dist_repo_argument_errors(self):
        """Test handle_dist_repo function with common arugment errors"""

        tests = [
            {
                'arg': [],
                'err_str': 'You must provide a tag to generate the repo from'
            },
            {
                'arg': [self.tag_name],
                'err_str': 'Please specify one or more GPG key IDs (or --allow-missing-signatures)'
            },
            {
                'arg': [
                    self.tag_name, self.fake_key,
                    '--allow-missing-signatures',
                    '--skip-missing-signatures'
                ],
                'err_str': 'allow_missing_signatures and skip_missing_signatures are mutually exclusive'
            }
        ]

        expected = ''
        for test in tests:
            expected = self.format_error_message(test['err_str'])
            self.assert_system_exit(
                handle_dist_repo,
                self.options,
                self.session,
                test['arg'],
                stderr=expected,
                activate_session=None)

        # Case 2. Tag Error
        self.session.getTag.return_value = {}
        expected = self.format_error_message('unknown tag %s' % self.tag_name)
        self.assert_system_exit(
            handle_dist_repo,
            self.options,
            self.session,
            [self.tag_name, self.fake_key],
            stderr=expected)

        # Case 3. Arch field is empty in Tag
        tag = copy.copy(self.TAG)
        tag.update({'arches': None})
        self.session.getTag.return_value = tag
        expected = self.format_error_message('No arches given and no arches associated with tag')
        self.assert_system_exit(
            handle_dist_repo,
            self.options,
            self.session,
            [self.tag_name, self.fake_key],
            stderr=expected)

    def test_handle_dist_repo_with_comp(self):
        comp_file = 'comp.xml'
        arguments = [self.tag_name, self.fake_key, '--comp', comp_file]

        # Error case: if file is not exist
        expected = self.format_error_message('could not find %s' % comp_file)
        with mock.patch('os.path.exists', return_value=False):
            self.assert_system_exit(
                handle_dist_repo,
                self.options,
                self.session,
                arguments,
                stderr=expected)

        self.resetMocks()
        self.session.uploadWrapper = lambda *args, **kwargs: print('uploadWrapper ...')
        expected = 'uploadWrapper ...\n\n'
        with mock.patch('os.path.exists', return_value=True):
            self.__run_test_handle_dist_repo(arguments, True, expected)

    def test_handle_dist_repo_with_multiarch_opt(self):
        arches = ['i386', 'x86_64', 'ppc', 'src']
        arguments = [self.tag_name, self.fake_key]
        for a in arches:
            arguments += ['--arch', a]

        expected = 'Warning: %s is not in the list of tag arches' % arches[0] + "\n"
        expected += 'Warning: %s is not in the list of tag arches' % arches[2] + "\n"
        expected += 'Warning: %s is not in the list of tag arches' % arches[3] + "\n"
        self.__run_test_handle_dist_repo(arguments, True, expected)

    @mock.patch('os.path.exists')
    def test_handle_dist_repo_with_multilib_opt(self, path_mock):
        lib = 'libmultiarch-1.0.0-fc26.rpm'
        arguments = [self.tag_name, self.fake_key, '--multilib', lib]

        # sanity checks
        # case 1. lib package not exist
        path_mock.return_value = False
        expected = self.format_error_message('could not find %s' % lib)
        self.assert_system_exit(
            handle_dist_repo,
            self.options,
            self.session,
            arguments,
            stderr=expected)

        # case 2. arch check
        path_mock.return_value = True
        arches = [('x86_64', 'i686'), ('s390x', 's390'), ('ppc64', 'ppc')]
        for arch in arches:
            expected = self.format_error_message(
                'The multilib arch (%s) must be included' % arch[1])
            self.assert_system_exit(
                handle_dist_repo,
                self.options,
                self.session,
                arguments + ['--arch', arch[0]],
                stderr=expected)

        # normal case
        self.session.uploadWrapper = lambda *args, **kwargs: print ('uploadWrapper ...')
        self.session.getTag.return_value.update({'arches': 'x86_64, i686'})
        expected = 'uploadWrapper ...\n\n'
        arguments += ['--arch', 'x86_64', '--arch', 'i686']
        self.__run_test_handle_dist_repo(arguments, True, expected)

    def test_handle_dist_repo_with_delta_rpms_opt(self):
        repos = ['test-repo1', 'test-repo2', '3']
        arguments = [self.tag_name, self.fake_key]
        for r in repos:
            arguments += ['--delta-rpms', r]

        # Error case: if repo is not exist
        self.session.getRepo.return_value = {}
        expected = self.format_error_message("Can't find repo for tag: %s" % "test-repo1")
        self.assert_system_exit(
                handle_dist_repo,
                self.options,
                self.session,
                arguments,
                stderr=expected)

        # Normal case, assume test-repo2 is expired
        self.session.getRepo.side_effect = [
            {'id': 1, 'name': 'test-repo1'},
            None,
            {'id': 2, 'name': 'test-repo2'},   # state is exprired repo
        ]
        self.__run_test_handle_dist_repo(arguments, True)

    def test_handle_dist_repo_help(self):
        """Test handle_dist_repo help message"""
        self.assert_help(
            handle_dist_repo,
            """Usage: %s dist-repo [options] <tag> <key_id> [<key_id> ...]

In normal mode, dist-repo behaves like any other koji task.
Sometimes you want to limit running distRepo tasks per tag to only
one. For such behaviour admin (with 'tag' permission) needs to
modify given tag's extra field 'distrepo.cancel_others' to True'
via 'koji edit-tag -x distrepo.cancel_others=True'

(Specify the --help option for a list of other options)

Options:
  -h, --help            show this help message and exit
  --allow-missing-signatures
                        For RPMs not signed with a desired key, fall back to
                        the primary copy
  -a ARCH, --arch=ARCH  Indicate an architecture to consider. The default is
                        all architectures associated with the given tag. This
                        option may be specified multiple times.
  --with-src            Also generate a src repo
  --split-debuginfo     Split debuginfo info a separate repo for each arch
  --comps=COMPS         Include a comps file in the repodata
  --delta-rpms=REPO     Create delta rpms. REPO can be the id of another dist
                        repo or the name of a tag that has a dist repo. May be
                        specified multiple times.
  --event=EVENT         Use tag content at event
  --volume=VOLUME       Generate repo on given volume
  --non-latest          Include older builds, not just the latest
  --multilib=CONFIG     Include multilib packages in the repository using the
                        given config file
  --noinherit           Do not consider tag inheritance
  --nowait              Do not wait for the task to complete
  --skip-missing-signatures
                        Skip RPMs not signed with the desired key(s)
  --zck                 Generate zchunk files as well as the standard repodata
  --zck-dict-dir=ZCK_DICT_DIR
                        Directory containing compression dictionaries for use
                        by zchunk (on builder)
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
