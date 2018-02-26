from __future__ import absolute_import
import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_unblock_group_req
from . import utils


class TestUnblockGroupReq(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.activate_session = mock.patch('koji_cli.commands.activate_session').start()

        self.error_format = """Usage: %s unblock-group-req [options] <tag> <group> <requirement>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_unblock_group_req(self):
        """Test handle_unblock_group_req function"""
        arguments = ['fedora-build', 'build', 'srpm-build']
        handle_unblock_group_req(self.options, self.session, arguments)
        self.session.groupReqListUnblock.assert_called_with(*arguments)
        self.activate_session.assert_called_with(self.session, self.options)

    def test_handle_unblock_group_req_argument_error(self):
        """Test handle_unblock_group_req function with wrong argument"""
        expected = self.format_error_message(
            "You must specify a tag name and two group names")
        for arg in [[], ['tag'], ['tag', 'grp', 'opt1', 'opt2']]:
            self.assert_system_exit(
                handle_unblock_group_req,
                self.options,
                self.session,
                arg,
                stderr=expected,
                activate_session=None)
        self.activate_session.assert_not_called()

    def test_handle_unblock_group_req_help(self):
        self.assert_help(
            handle_unblock_group_req,
            """Usage: %s unblock-group-req [options] <tag> <group> <requirement>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
