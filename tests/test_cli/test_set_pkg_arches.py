from __future__ import absolute_import
try:
    from unittest import mock
except ImportError:
    import mock
import six
import unittest

from koji_cli.commands import handle_set_pkg_arches
from . import utils


class TestSetPkgArches(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s set-pkg-arches [options] <arches> <tag> <package> [<package> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_set_pkg_arches(
            self,
            activate_session_mock,
            stdout):
        """Test handle_set_pkg_arches function"""
        session = mock.MagicMock()
        options = mock.MagicMock()
        arguments = ['x86_64', 'tag', '--force', 'bash', 'less', 'sed']

        expected = self.format_error_message(
            "Please specify an archlist, a tag, and at least one package")

        # Case 1. argument error
        self.assert_system_exit(
            handle_set_pkg_arches,
            options,
            session,
            [],
            stderr=expected,
            activate_session=None)
        activate_session_mock.assert_not_called()

        # Case 2. run set arch to x86_64
        multicall = mock.MagicMock()
        multicall.__enter__.return_value = multicall
        session.multicall.return_value = multicall
        calls = [mock.call('tag', pkg, 'x86_64', force=True) for pkg in arguments[3:]]
        handle_set_pkg_arches(options, session, arguments)
        activate_session_mock.assert_called_with(session, options)
        multicall.packageListSetArches.assert_has_calls(calls)
        self.assert_console_message(stdout, '')

    def test_handle_set_pkg_arches_help(self):
        self.assert_help(
            handle_set_pkg_arches,
            """Usage: %s set-pkg-arches [options] <arches> <tag> <package> [<package> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
  --force     Force operation
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
