from __future__ import absolute_import
import mock
import os
import time
import locale
from six.moves import StringIO
import copy

import koji
from koji_cli.commands import anon_handle_hostinfo
from . import utils


class TestHostinfo(utils.CliTestCase):
    def setUp(self):
        # force locale to compare 'expect' value
        self.maxDiff = None
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
                         'enabled': True,
                         'id': 1,
                         'name': 'kojibuilder',
                         'ready': True,
                         'task_load': 0.0,
                         'user_id': 2,
                         'comment': 'test-comment',
                         'description': 'test-description'}
        self.last_update = 1615875554.862938
        self.list_channels = [{'id': 1, 'name': 'default'}, {'id': 2, 'name': 'createrepo'}]
        self.error_format = """Usage: %s hostinfo [options] <hostname> [<hostname> ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.ensure_connection_mock = mock.patch('koji_cli.commands.ensure_connection').start()

    def tearDown(self):
        locale.resetlocale()
        if self.original_timezone is None:
            del os.environ['TZ']
        else:
            os.environ['TZ'] = self.original_timezone
            time.tzset()

    def test_hostinfo_without_option(self):
        self.session.getChannel.return_value = None
        self.assert_system_exit(
            anon_handle_hostinfo,
            self.options, self.session, [],
            stderr=self.format_error_message('Please specify a host'),
            exit_code=2,
            activate_session=None)
        self.session.getHost.assert_not_called()
        self.session.getLastHostUpdate.assert_not_called()
        self.session.listChannels.assert_not_called()
        self.ensure_connection_mock.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_hostinfo_valid(self, stdout):
        expected = """Name: kojibuilder
ID: 1
Arches: x86_64
Capacity: 2.0
Task Load: 0.00
Description: test-description
Comment: test-comment
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
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.assertEqual(self.session.listBuildroots.call_count, 3)

    def test_hostinfo_more_hosts_with_non_exit_host(self):
        hostinfo = copy.deepcopy(self.hostinfo)
        hostinfo['description'] = None
        hostinfo['comment'] = None
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
        self.session.getHost.side_effect = [None, hostinfo]
        self.session.getLastHostUpdate.return_value = self.last_update
        self.session.listChannels.return_value = self.list_channels
        self.session.listBuildroots.return_value = []
        self.assert_system_exit(
            anon_handle_hostinfo,
            self.options, self.session, [non_exist_hostname, hostname],
            stderr="No such host: %s\n\n" % non_exist_hostname,
            stdout=expected_stdout,
            exit_code=1,
            activate_session=None)
        self.assertEqual(self.session.getHost.call_count, 2)
        self.session.getLastHostUpdate.assert_called_once_with(self.hostinfo['id'], ts=True)
        self.session.listChannels.assert_called_once_with(hostID=self.hostinfo['id'])
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.assertEqual(self.session.listBuildroots.call_count, 3)

    def test_hostinfo_non_exist_host(self):
        hostname = '1111'
        self.session.getHost.return_value = None
        self.session.getLastHostUpdate.return_value = None
        self.assert_system_exit(
            anon_handle_hostinfo,
            self.options, self.session, [hostname],
            stderr="No such host: %s\n\n" % hostname,
            stdout='',
            exit_code=1,
            activate_session=None)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_hostinfo_valid_param_error(self, stdout):
        expected = """Name: kojibuilder
ID: 1
Arches: x86_64
Capacity: 2.0
Task Load: 0.00
Description: test-description
Comment: test-comment
Enabled: yes
Ready: yes
Last Update: Tue, 16 Mar 2021 06:19:14 UTC
Channels: default createrepo
Active Buildroots:
None
"""
        self.session.getHost.return_value = self.hostinfo
        self.session.getLastHostUpdate.side_effect = [koji.ParameterError, self.last_update]
        self.session.listChannels.return_value = self.list_channels
        rv = anon_handle_hostinfo(self.options, self.session, [self.hostinfo['name']])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.getHost.assert_called_once_with(self.hostinfo['name'])
        self.session.listChannels.assert_called_once_with(hostID=self.hostinfo['id'])
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.assertEqual(self.session.listBuildroots.call_count, 3)
