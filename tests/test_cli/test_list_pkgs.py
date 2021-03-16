from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_list_pkgs
from . import utils


class TestListPkgs(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_pkgs_non_exist_tag(self, stderr):
        tag = 'test-tag'
        expected = "Usage: %s list-pkgs [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such tag: %s\n" % (self.progname, self.progname, tag)
        self.session.getTag.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_pkgs(self.options, self.session, ['--tag', tag])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_pkgs_non_exist_owner(self, stderr):
        owner = 'test-owner'
        expected = "Usage: %s list-pkgs [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such user: %s\n" % (self.progname, self.progname, owner)
        self.session.getUser.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_pkgs(self.options, self.session, ['--owner', owner])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
