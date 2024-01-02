from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_untag_build
from . import utils


class TestUntagBuild(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.tag_info = {'arches': 'x86_64',
                         'extra': {},
                         'id': 1,
                         'locked': False,
                         'maven_include_all': False,
                         'maven_support': False,
                         'name': 'test-tag',
                         'perm': None,
                         'perm_id': None}
        self.tag = 'test-tag'
        self.pkg_name = 'test-package'
        self.tag_listing = \
            {'tag_listing': [{'active': True, 'build_id': 3, 'create_event': 1357, 'epoch': 1,
                              'name': 'test-package', 'release': '1.f35', 'tag.name': 'test-tag',
                              'tag_id': 460, 'version': '1.6'},
                             {'active': True, 'build_id': 3, 'create_event': 1357, 'epoch': 1,
                              'name': 'test-package', 'release': '1.f35', 'tag.name': 'test-tag',
                              'tag_id': 460, 'version': '1.1'}]}

    def __vm(self, result):
        m = koji.VirtualCall('mcall_method', [], {})
        if isinstance(result, dict) and result.get('faultCode'):
            m._result = result
        else:
            m._result = (result,)
        return m

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_untag_build_without_option(self, stderr):
        expected = "Usage: %s untag-build [options] <tag> <pkg> [<pkg> ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: This command takes at least two arguments: " \
                   "a tag name/ID and one or more package " \
                   "n-v-r's or package names\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_untag_build(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.activate_session_mock.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.queryHistory.assert_not_called()
        self.session.untagBuild.assert_not_called()

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_untag_build_without_option_non_latest_force(self, stderr):
        expected = "Usage: %s untag-build [options] <tag> <pkg> [<pkg> ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Please specify a tag\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_untag_build(self.options, self.session, ['--non-latest', '--force'])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.activate_session_mock.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.queryHistory.assert_not_called()
        self.session.untagBuild.assert_not_called()

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_untag_build_non_exist_tag(self, stderr):
        expected = "Usage: %s untag-build [options] <tag> <pkg> [<pkg> ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such tag: %s\n" % (self.progname, self.progname, self.tag)
        self.session.getTag.return_value = None
        with self.assertRaises(SystemExit) as ex:
            handle_untag_build(self.options, self.session, [self.tag, self.pkg_name])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(self.tag)
        self.session.queryHistory.assert_not_called()
        self.session.untagBuild.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_untag_build_all(self, stdout):
        self.session.getTag.return_value = self.tag_info
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.queryHistory.return_value = self.__vm(self.tag_listing)

        handle_untag_build(self.options, self.session, ['--all', self.tag, self.pkg_name])
        expected = ''
        self.assert_console_message(stdout, expected)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(self.tag)
        self.session.multicall.assert_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_untag_build_all_verbose(self, stdout):
        self.session.getTag.return_value = self.tag_info
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.queryHistory.return_value = self.__vm(self.tag_listing)
        handle_untag_build(self.options, self.session,
                           ['--all', '--verbose', self.tag, self.pkg_name])
        expected = 'untagging test-package-1.1-1.f35\nuntagging test-package-1.6-1.f35\n'
        self.assert_console_message(stdout, expected)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(self.tag)
        self.session.multicall.assert_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_untag_build_all_non_latest_verbose(self, stdout):
        self.session.getTag.return_value = self.tag_info
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.queryHistory.return_value = self.__vm(self.tag_listing)
        handle_untag_build(self.options, self.session,
                           ['--non-latest', '--verbose', self.tag, self.pkg_name])
        expected = 'Leaving latest build for package test-package: test-package-1.6-1.f35\n' \
                   'untagging test-package-1.1-1.f35\n'
        self.assert_console_message(stdout, expected)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(self.tag)
        self.session.multicall.assert_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_untag_build_all_non_latest_verbose_only_one_pkg(self, stdout):
        self.session.getTag.return_value = self.tag_info
        tag_listing = \
            {'tag_listing': [{'active': True, 'build_id': 3, 'create_event': 1357, 'epoch': 1,
                              'name': 'test-package', 'release': '1.f35',
                              'tag.name': 'test-tag', 'tag_id': 460, 'version': '1.6'}]}
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.queryHistory.return_value = self.__vm(tag_listing)
        handle_untag_build(self.options, self.session,
                           ['--non-latest', '--verbose', self.tag, self.pkg_name])
        expected = 'Leaving latest build for package test-package: test-package-1.6-1.f35\n'
        self.assert_console_message(stdout, expected)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(self.tag)
        self.session.multicall.assert_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_untag_build_all_non_latest_force_test(self, stdout):
        self.session.getTag.return_value = self.tag_info
        self.session.queryHistory.return_value = self.tag_listing
        handle_untag_build(self.options, self.session,
                           ['--non-latest', '--force', '--test', self.tag])
        expected = 'would have untagged test-package-1.1-1.f35\n'
        self.assert_console_message(stdout, expected)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.getTag.assert_called_once_with(self.tag)
        self.session.multicall.assert_called_once()
        self.session.untagBuild.assert_not_called()

    def test_untag_build_help(self):
        self.assert_help(
            handle_untag_build,
            """Usage: %s untag-build [options] <tag> <pkg> [<pkg> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help     show this help message and exit
  --all          untag all versions of the package in this tag, pkg is package
                 name
  --non-latest   untag all versions of the package in this tag except the
                 latest, pkg is package name
  -n, --test     test mode
  -v, --verbose  print details
  --force        force operation
""" % self.progname)
