from __future__ import absolute_import
try:
    from unittest import mock
except ImportError:
    import mock
import unittest

from koji_cli.commands import handle_add_group_pkg
from . import utils


class TestAddGroupPkg(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.activate_session = mock.patch('koji_cli.commands.activate_session').start()

        self.error_format = """Usage: %s add-group-pkg [options] <tag> <group> <pkg> [<pkg> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_add_group_pkg(self):
        """Test handle_add_group_pkg function"""
        arguments = ['fedora-build', 'build']
        for pkg in [['bash'], ['sed', 'less', 'awk']]:
            handle_add_group_pkg(self.options, self.session, arguments + pkg)
            calls = [mock.call(arguments[0], arguments[1], p) for p in pkg]
            self.session.groupPackageListAdd.assert_has_calls(calls)
            self.activate_session.assert_called_with(self.session, self.options)

    def test_handle_add_group_pkg_argument_error(self):
        """Test handle_add_group_pkg function with wrong argument"""
        expected = self.format_error_message(
            "You must specify a tag name, group name, and one or more package names")
        for arg in [[], ['tag'], ['tag', 'grp']]:
            self.assert_system_exit(
                handle_add_group_pkg,
                self.options,
                self.session,
                arg,
                stderr=expected,
                activate_session=None)
        self.activate_session.assert_not_called()

    def test_handle_add_group_pkg_help(self):
        self.assert_help(
            handle_add_group_pkg,
            """Usage: %s add-group-pkg [options] <tag> <group> <pkg> [<pkg> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
