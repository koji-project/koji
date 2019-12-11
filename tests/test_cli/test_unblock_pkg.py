from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest


from koji_cli.commands import handle_unblock_pkg
from . import utils


class TestUnblockPkg(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s unblock-pkg [options] <tag> <package> [<package> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_unblock_pkg(
            self,
            activate_session_mock,
            stdout):
        """Test handle_unblock_pkg function"""
        session = mock.MagicMock()
        options = mock.MagicMock()
        arguments = ['tag', 'bash', 'less', 'sed']

        expected = self.format_error_message(
            "Please specify a tag and at least one package")

        # Case 1. argument error
        self.assert_system_exit(
            handle_unblock_pkg,
            options,
            session,
            [],
            stderr=expected,
            activate_session=None)
        activate_session_mock.assert_not_called()

        # Case 2. run unlock
        multicall = mock.MagicMock()
        multicall.__enter__.return_value = multicall
        session.multicall.return_value = multicall
        calls = [mock.call('tag', pkg) for pkg in arguments[1:]]
        handle_unblock_pkg(options, session, arguments)
        activate_session_mock.assert_called_with(session, options)
        multicall.packageListUnblock.assert_has_calls(calls)
        self.assert_console_message(stdout, '')

    def test_handle_unblock_pkg_help(self):
        self.assert_help(
            handle_unblock_pkg,
            """Usage: %s unblock-pkg [options] <tag> <package> [<package> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
