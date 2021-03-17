from __future__ import absolute_import
import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_hostinfo
from . import utils


class TestHostinfo(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
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
        self.last_update = '2021-03-16 06:19:14.862938+00:00'
        self.list_channels = [{'id': 1, 'name': 'default'}, {'id': 2, 'name': 'createrepo'}]

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
Last Update: 2021-03-16 06:19:14
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
        self.session.getLastHostUpdate.assert_called_once_with(self.hostinfo['id'])
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
