from __future__ import absolute_import
import mock
import unittest
from six.moves import StringIO

from koji_cli.commands import anon_handle_list_untagged
from . import utils


class TestListUntagged(utils.CliTestCase):
    def setUp(self):
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
