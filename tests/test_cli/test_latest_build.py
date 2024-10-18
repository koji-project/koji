from __future__ import absolute_import

import unittest

try:
    from unittest import mock
except ImportError:
    import mock

from koji_cli.commands import anon_handle_latest_build
from . import utils


class TestLatestBuild(utils.CliTestCase):

    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.session = mock.MagicMock()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.ensure_connection = mock.patch('koji_cli.commands.ensure_connection').start()
        self.tag_name = 'test-tag'
        self.pkg_name = 'test-pkg'
        self.expected_part_help = """Usage: %s latest-build [options] <tag> <package> [<package> ...]

The first option should be the name of a tag, not the name of a build target.
If you want to know the latest build in buildroots for a given build target,
then you should use the name of the build tag for that target. You can find
this value by running '%s list-targets --name=<target>'

More information on tags and build targets can be found in the documentation.
https://docs.pagure.org/koji/HOWTO/#package-organization
(Specify the --help global option for a list of other help options)

""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_latest_build_without_args(self):
        expected = "%s: error: A tag name must be specified\n" % self.progname
        self.assert_system_exit(
            anon_handle_latest_build,
            self.options, self.session, [],
            stdout='',
            stderr=self.expected_part_help + expected,
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.ensure_connection.assert_not_called()

    def test_handle_latest_build_more_args(self):
        expected = "%s: error: A tag name and package name must be specified\n" % self.progname
        self.assert_system_exit(
            anon_handle_latest_build,
            self.options, self.session, [self.tag_name],
            stdout='',
            stderr=self.expected_part_help + expected,
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.ensure_connection.assert_called_once()

    def test_handle_latest_build_all_and_pkg(self):
        expected = "%s: error: A package name may not be combined with --all\n" % self.progname
        self.assert_system_exit(
            anon_handle_latest_build,
            self.options, self.session, ['--all', self.tag_name, self.pkg_name],
            stdout='',
            stderr=self.expected_part_help + expected,
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()
        self.ensure_connection.assert_called_once()

    def test_handle_latest_build_help(self):
        self.assert_help(
            anon_handle_latest_build,
            self.expected_part_help + """Options:
  -h, --help   show this help message and exit
  --arch=ARCH  List all of the latest packages for this arch
  --all        List all of the latest packages for this tag
  --quiet      Do not print the header information
  --paths      Show the file paths
  --type=TYPE  Show builds of the given type only. Currently supported types:
               maven, win, image, or any custom content generator btypes
""")


if __name__ == '__main__':
    unittest.main()
