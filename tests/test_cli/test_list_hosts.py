from __future__ import absolute_import
import mock
import os
import time
import locale
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_list_hosts
from . import utils


class TestListHosts(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        # force locale to compare 'expect' value
        locale.setlocale(locale.LC_ALL, ('en_US', 'UTF-8'))
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.original_timezone = os.environ.get('TZ')
        os.environ['TZ'] = 'UTC'
        time.tzset()
        self.ensure_connection_mock = mock.patch('koji_cli.commands.ensure_connection').start()
        self.error_format = """Usage: %s list-hosts [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.list_hosts = [{'arches': 'x86_64',
                            'capacity': 2.0,
                            'comment': 'test-comment',
                            'description': 'test-description',
                            'enabled': False,
                            'id': 1,
                            'name': 'kojibuilder',
                            'ready': True,
                            'task_load': 0.0,
                            'user_id': 2}]

    def tearDown(self):
        locale.setlocale(locale.LC_ALL, "")
        if self.original_timezone is None:
            del os.environ['TZ']
        else:
            os.environ['TZ'] = self.original_timezone
        time.tzset()
        mock.patch.stopall()

    def __vm(self, result):
        m = koji.VirtualCall('mcall_method', [], {})
        if isinstance(result, dict) and result.get('faultCode'):
            m._result = result
        else:
            m._result = (result,)
        return m

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_hosts_valid_without_quiet(self, stdout):
        self.options.quiet = False
        host_update = 1615875554.862938
        expected = """Hostname    Enb Rdy Load/Cap  Arches           Last Update                         
-----------------------------------------------------------------------------------
kojibuilder N   Y    0.0/2.0  x86_64           Tue, 16 Mar 2021 06:19:14 UTC      
"""

        self.session.getLastHostUpdate.return_value = host_update
        self.session.multiCall.return_value = [[host_update]]
        self.session.listHosts.return_value = self.list_hosts
        rv = anon_handle_list_hosts(self.options, self.session, [])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.listHosts.assert_called_once_with()
        self.session.getLastHostUpdate.assert_called_once_with(self.list_hosts[0]['id'], ts=True)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    def test_list_hosts_non_exist_channel(self):
        channel = 'test-channel'
        self.session.getChannel.return_value = None
        self.assert_system_exit(
            anon_handle_list_hosts,
            self.options, self.session, ['--channel', channel],
            stderr=self.format_error_message('No such channel: %s' % channel),
            exit_code=2,
            activate_session=None)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_hosts_empty(self, stderr):
        expected = "No hosts found.\n"
        self.session.listHosts.return_value = []
        anon_handle_list_hosts(self.options, self.session, [])
        self.assert_console_message(stderr, expected)
        self.session.listHosts.assert_called_once_with()
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_hosts_with_arch(self, stdout):
        host_update = 1615875554.862938
        expected = "kojibuilder N   Y    0.0/2.0  x86_64           " \
                   "Tue, 16 Mar 2021 06:19:14 UTC      \n"

        self.session.getLastHostUpdate.return_value = host_update
        self.session.multiCall.return_value = [[host_update]]
        self.session.listHosts.return_value = self.list_hosts
        rv = anon_handle_list_hosts(self.options, self.session, ['--arch', 'x86_64'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.listHosts.assert_called_once_with(arches=['x86_64'])
        self.session.getLastHostUpdate.assert_called_once_with(self.list_hosts[0]['id'], ts=True)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_hosts_with_arch_not_used(self, stdout):
        expected = ""

        self.session.listHosts.return_value = []
        rv = anon_handle_list_hosts(self.options, self.session, ['--arch', 'ppc'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.listHosts.assert_called_once_with(arches=['ppc'])
        self.session.getLastHostUpdate.assert_not_called()
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_hosts_with_ready(self, stdout):
        host_update = None
        expected = "kojibuilder N   Y    0.0/2.0  x86_64           " \
                   "-                                  \n"

        self.session.getLastHostUpdate.return_value = host_update
        self.session.multiCall.return_value = [[host_update]]
        self.session.listHosts.return_value = self.list_hosts
        rv = anon_handle_list_hosts(self.options, self.session, ['--ready'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.listHosts.assert_called_once_with(ready=True)
        self.session.getLastHostUpdate.assert_called_once_with(self.list_hosts[0]['id'], ts=True)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_hosts_with_not_ready(self, stdout):
        expected = ""
        self.session.listHosts.return_value = []
        rv = anon_handle_list_hosts(self.options, self.session, ['--not-ready'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.listHosts.assert_called_once_with(ready=False)
        self.session.getLastHostUpdate.assert_not_called()
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_hosts_with_enabled(self, stdout):
        expected = ""

        self.session.listHosts.return_value = []
        rv = anon_handle_list_hosts(self.options, self.session, ['--enabled'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.listHosts.assert_called_once_with(enabled=True)
        self.session.getLastHostUpdate.assert_not_called()
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_hosts_with_not_enabled(self, stdout):
        host_update = 1615875554.862938
        expected = "kojibuilder N   Y    0.0/2.0  x86_64           " \
                   "Tue, 16 Mar 2021 06:19:14 UTC      \n"

        self.session.getLastHostUpdate.return_value = host_update
        self.session.multiCall.return_value = [[host_update]]
        self.session.listHosts.return_value = self.list_hosts
        rv = anon_handle_list_hosts(self.options, self.session, ['--not-enabled'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.listHosts.assert_called_once_with(enabled=False)
        self.session.getLastHostUpdate.assert_called_once_with(self.list_hosts[0]['id'], ts=True)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_hosts_param_error_get_last_host_update(self, stdout):
        # host_update = 1615875554.862938
        host_update = '2021-03-16 06:19:14.862938-00:00'
        expected = "kojibuilder N   Y    0.0/2.0  x86_64           " \
                   "Tue, 16 Mar 2021 06:19:14 UTC      \n"

        # simulate an older hub that doesn't support the ts option for getLastHostUpdate
        self.session.getLastHostUpdate.side_effect = [koji.ParameterError, host_update]
        self.session.multiCall.return_value = [[host_update]]
        self.session.listHosts.return_value = self.list_hosts
        rv = anon_handle_list_hosts(self.options, self.session, ['--ready'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.listHosts.assert_called_once_with(ready=True)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_hosts_valid_without_quiet_description_and_comment(self, stdout):
        self.options.quiet = False
        host_update = 1615875554.862938
        expected = "Hostname    Enb Rdy Load/Cap  Arches           Last Update" \
                   "                         Description                                        " \
                   "Comment                                            \n" \
                   "---------------------------------------------------------------------------" \
                   "---------------------------------------------------------------------------" \
                   "-----------------------------------\n" \
                   "kojibuilder N   Y    0.0/2.0  x86_64           Tue, 16 Mar 2021 06:19:14 UTC" \
                   "       test-description                                   test-comment" \
                   "                                      \n"

        self.session.getLastHostUpdate.return_value = host_update
        self.session.multiCall.return_value = [[host_update]]
        self.session.listHosts.return_value = self.list_hosts
        rv = anon_handle_list_hosts(self.options, self.session, ['--description', '--comment'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.listHosts.assert_called_once_with()
        self.session.getLastHostUpdate.assert_called_once_with(self.list_hosts[0]['id'], ts=True)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_hosts_valid_description_and_comment(self, stdout):
        host_update = 1615875554.862938
        expected = "kojibuilder N   Y    0.0/2.0  x86_64           Tue, 16 Mar 2021 06:19:14 UTC" \
                   "       test-description                                   test-comment" \
                   "                                      \n"

        self.session.getLastHostUpdate.return_value = host_update
        self.session.multiCall.return_value = [[host_update]]
        self.session.listHosts.return_value = self.list_hosts
        rv = anon_handle_list_hosts(self.options, self.session, ['--description', '--comment'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.listHosts.assert_called_once_with()
        self.session.getLastHostUpdate.assert_called_once_with(self.list_hosts[0]['id'], ts=True)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_hosts_with_show_channels(self, stdout):
        self.options.quiet = False
        host_update = 1615875554.862938
        expected = """Hostname    Enb Rdy Load/Cap  Arches           Last Update                         Channels
-------------------------------------------------------------------------------------------
kojibuilder N   Y    0.0/2.0  x86_64           Tue, 16 Mar 2021 06:19:14 UTC       *test,default\n"""
        list_channels = [
            {'id': 1, 'name': 'default', 'enabled': True, 'comment': 'test-comment-1',
             'description': 'test-description-1'},
            {'id': 2, 'name': 'test', 'enabled': False, 'comment': 'test-comment-2',
             'description': 'test-description-2'},
        ]

        self.session.getLastHostUpdate.return_value = host_update
        self.session.multiCall.return_value = [[host_update]]
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.listChannels.return_value = self.__vm(list_channels)

        self.session.listHosts.return_value = self.list_hosts
        rv = anon_handle_list_hosts(self.options, self.session, ['--show-channels'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.listHosts.assert_called_once_with()
        self.session.getLastHostUpdate.assert_called_once_with(self.list_hosts[0]['id'], ts=True)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.listChannels.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_hosts_with_show_channels_empty(self, stdout):
        self.options.quiet = False
        host_update = 1615875554.862938
        expected = """Hostname    Enb Rdy Load/Cap  Arches           Last Update                         Channels
-------------------------------------------------------------------------------------------
kojibuilder N   Y    0.0/2.0  x86_64           Tue, 16 Mar 2021 06:19:14 UTC       \n"""
        list_channels = []

        self.session.getLastHostUpdate.return_value = host_update
        self.session.multiCall.return_value = [[host_update]]
        mcall = self.session.multicall.return_value.__enter__.return_value
        mcall.listChannels.return_value = self.__vm(list_channels)

        self.session.listHosts.return_value = self.list_hosts
        rv = anon_handle_list_hosts(self.options, self.session, ['--show-channels'])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.listHosts.assert_called_once_with()
        self.session.getLastHostUpdate.assert_called_once_with(self.list_hosts[0]['id'], ts=True)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.session.listChannels.assert_not_called()

    def test_list_hosts_help(self):
        self.assert_help(
            anon_handle_list_hosts,
            """Usage: %s list-hosts [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help         show this help message and exit
  --arch=ARCH        Specify an architecture
  --channel=CHANNEL  Specify a channel
  --ready            Limit to ready hosts
  --not-ready        Limit to not ready hosts
  --enabled          Limit to enabled hosts
  --not-enabled      Limit to not enabled hosts
  --disabled         Alias for --not-enabled
  --quiet            Do not print header information
  --show-channels    Show host's channels
  --comment          Show comments
  --description      Show descriptions
""" % self.progname)
