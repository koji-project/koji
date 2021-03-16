from __future__ import absolute_import
import mock
import os
import time
import locale
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_hostinfo
from . import utils


class TestHostinfo(utils.CliTestCase):
    def setUp(self):
        # force locale to compare 'expect' value
        locale.setlocale(locale.LC_ALL, ('en_US', 'UTF-8'))
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.original_timezone = os.environ.get('TZ')
        os.environ['TZ'] = 'UTC'
        time.tzset()
        self.hostinfo = {'arches': 'x86_64',
                         'capacity': 2.0,
                         'comment': None,
                         'description': None,
                         'enabled': True,
                         'id': 1,
                         'name': 'kojibuilder',
                         'ready': True,
                         'task_load': 0.0,
                         'user_id': 2}
        self.last_update = 1615875554.862938
        self.list_channels = [{'id': 1, 'name': 'default'}, {'id': 2, 'name': 'createrepo'}]

    def tearDown(self):
        locale.resetlocale()
        if self.original_timezone is None:
            del os.environ['TZ']
        else:
            os.environ['TZ'] = self.original_timezone
            time.tzset()

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_hostinfo_without_option(self, stderr):
        expected = "Usage: %s hostinfo [options] <hostname> [<hostname> ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Please specify a host\n" % (self.progname, self.progname)
        self.session.getChannel.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_hostinfo(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_hostinfo_valid(self, stdout):
        expected = """Name: kojibuilder
ID: 1
Arches: x86_64
Capacity: 2.0
Task Load: 0.00
Description:
Comment:
Enabled: yes
Ready: yes
Last Update: Tue, 16 Mar 2021 06:19:14 UTC
Channels: default createrepo
Active Buildroots:
None
"""
        self.session.getHost.return_value = self.hostinfo
        self.session.getLastHostUpdate.return_value = self.last_update
        self.session.listChannels.return_value = self.list_channels
        rv = anon_handle_hostinfo(self.options, self.session, [self.hostinfo['name']])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.getHost.assert_called_once_with(self.hostinfo['name'])
        self.session.getLastHostUpdate.assert_called_once_with(self.hostinfo['id'], ts=True)
        self.session.listChannels.assert_called_once_with(hostID=self.hostinfo['id'])
        self.assertEqual(self.session.listBuildroots.call_count, 3)

    @mock.patch('sys.stderr', new_callable=StringIO)
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_hostinfo_more_hosts_with_non_exit_host(self, stdout, stderr):
        hostname = 'kojibuilder'
        non_exist_hostname = 'testhost'
        expected_stdout = """Name: kojibuilder
ID: 1
Arches: x86_64
Capacity: 2.0
Task Load: 0.00
Description:
Comment:
Enabled: yes
Ready: yes
Last Update: Tue, 16 Mar 2021 06:19:14 UTC
Channels: default createrepo
Active Buildroots:
None
"""
        expected_error = "No such host: %s\n\n" % non_exist_hostname
        self.session.getHost.side_effect = [None, self.hostinfo]
        self.session.getLastHostUpdate.return_value = self.last_update
        self.session.listChannels.return_value = self.list_channels
        self.session.listBuildroots.return_value = []
        with self.assertRaises(SystemExit) as ex:
            anon_handle_hostinfo(self.options, self.session, [non_exist_hostname, hostname])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stdout, expected_stdout)
        self.assert_console_message(stderr, expected_error)
        self.assertEqual(self.session.getHost.call_count, 2)
        self.session.getLastHostUpdate.assert_called_once_with(self.hostinfo['id'], ts=True)
        self.session.listChannels.assert_called_once_with(hostID=self.hostinfo['id'])
        self.assertEqual(self.session.listBuildroots.call_count, 3)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_hostinfo_non_exist_host(self, stderr):
        hostname = 'testhost'
        expected = "No such host: %s\n\n" % hostname
        self.session.getHost.return_value = None
        self.session.getLastHostUpdate.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_hostinfo(self.options, self.session, [hostname])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)
