from __future__ import absolute_import
import koji
try:
    from unittest import mock
except ImportError:
    import mock
import unittest
from six.moves import StringIO

from koji_cli.commands import anon_handle_list_untagged
from . import utils


class TestListUntagged(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.untagged_values = [{'id': 1,
                                 'name': 'test-package-1234',
                                 'release': '11',
                                 'version': '1.1'},
                                {'id': 2,
                                 'name': 'test-package-1234',
                                 'release': '99',
                                 'version': '1.33'}
                                ]

    def __vm(self, result):
        m = koji.VirtualCall('mcall_method', [], {})
        if isinstance(result, dict) and result.get('faultCode'):
            m._result = result
        else:
            m._result = (result,)
        return m

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_untagged_without_arguments(self, ensure_connection_mock,
                                             stdout):
        package_name = 'test-package-1234'

        self.session.untaggedBuilds.return_value = self.untagged_values
        expected = "\n".join([u['name'] + '-' + u['version'] + '-' +
                              u['release'] for u in self.untagged_values]) + "\n"
        anon_handle_list_untagged(self.options, self.session, [package_name])
        self.assert_console_message(stdout, expected)

    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_untagged_more_arguments(self, ensure_connection_mock):
        packages_name = ['test-package-1', 'test-package-2']
        expected = """Usage: %s list-untagged [options] [<package>]
(Specify the --help global option for a list of other help options)

%s: error: Only one package name may be specified\n""" % (self.progname,
                                                          self.progname)
        self.assert_system_exit(
            anon_handle_list_untagged,
            self.options,
            self.session,
            [packages_name[0], packages_name[0]],
            stderr=expected,
            activate_session=None)

    @mock.patch('sys.stderr', new_callable=StringIO)
    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_untagged_package(self, ensure_connection, stdout, stderr):
        # test case when package is existing
        package_name = 'test-package-1234'

        self.session.untaggedBuilds.return_value = self.untagged_values
        expected = "\n".join([u['name'] + '-' + u['version'] + '-' +
                              u['release'] for u in self.untagged_values]) + "\n"
        anon_handle_list_untagged(self.options, self.session, [package_name])
        self.assert_console_message(stdout, expected)

        self.session.untaggedBuilds.reset_mock()

        # test case when package is not existing
        package_name = 'test-package'
        expected = "No such package: %s" % package_name + "\n"
        self.session.untaggedBuilds.return_value = []
        self.session.getPackageID.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_untagged(self.options, self.session,
                                      [package_name])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_untagged_package_path(self, ensure_connection, stdout):
        # test case when package is existing
        package_name = 'test-package-1234'

        self.session.untaggedBuilds.return_value = self.untagged_values
        expected = "\n".join(['/mnt/koji/packages/' + u['name'] + '/' +
                              u['version'] + '/' + u['release']
                              for u in self.untagged_values]) + "\n"
        anon_handle_list_untagged(self.options, self.session,
                                  ['--paths', package_name])
        self.assert_console_message(stdout, expected)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_untagged_package_show_references(self, ensure_connection, stdout):
        # test case when package is existing
        rpms = [{'rpm_id': 123}, {'rpm_id': 125}]
        archives = [{'archive_id': 999}, {'archive_id': 888}]
        components = [{'archive_id': 999, 'rpm_id': 125}]
        build_references = {'tags': [{'name': 'tag-48rj15ma3a', 'tag_id': 2}],
                            'rpms': rpms,
                            'component_of': components,
                            'archives': archives,
                            'last_used': None,
                            'images': []}
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.buildReferences.return_value = self.__vm(build_references)
        package_name = 'test-package-1234'

        self.session.untaggedBuilds.return_value = self.untagged_values
        list_untagged = [u['name'] + '-' + u['version'] + '-' + u['release']
                         for u in self.untagged_values]
        expected = """(Showing build references)
%s rpms: %s, images/archives: %s, archives buildroots: %s
%s rpms: %s, images/archives: %s, archives buildroots: %s
""" % (list_untagged[0], rpms, components, archives, list_untagged[1], rpms, components, archives)
        anon_handle_list_untagged(self.options, self.session,
                                  ['--show-references', package_name])
        self.assert_console_message(stdout, expected)

    def test_handle_list_history_help(self):
        self.assert_help(
            anon_handle_list_untagged,
            """Usage: %s list-untagged [options] [<package>]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help         show this help message and exit
  --paths            Show the file paths
  --show-references  Show build references
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
