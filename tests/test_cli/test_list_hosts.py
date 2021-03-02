from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_list_hosts
from . import utils


class TestListHosts(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_pkgs_non_exist_channel(self, stderr):
        channel = 'test-channel'
        expected = "Usage: %s list-hosts [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such channel: %s\n" % (self.progname, self.progname, channel)
        self.session.getChannel.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_hosts(self.options, self.session, ['--channel', channel])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
