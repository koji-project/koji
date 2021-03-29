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
        # force locale to compare 'expect' value
        locale.setlocale(locale.LC_ALL, ('en_US', 'UTF-8'))
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.original_timezone = os.environ.get('TZ')
        os.environ['TZ'] = 'UTC'
        time.tzset()

    def tearDown(self):
        locale.resetlocale()
        if self.original_timezone is None:
            del os.environ['TZ']
        else:
            os.environ['TZ'] = self.original_timezone
            time.tzset()

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_hosts_valid(self, ensure_connection, stdout):
        host_update = 1615875554.862938
        expected = """kojibuilder Y   Y    0.0/2.0  x86_64           Tue, 16 Mar 2021 06:19:14 UTC
"""
        list_hosts = [{'arches': 'x86_64',
                       'capacity': 2.0,
                       'comment': None,
                       'description': None,
                       'enabled': True,
                       'id': 1,
                       'name': 'kojibuilder',
                       'ready': True,
                       'task_load': 0.0,
                       'user_id': 2}]
        self.session.getLastHostUpdate.return_value = host_update
        self.session.multiCall.return_value = [[host_update]]
        self.session.listHosts.return_value = list_hosts
        rv = anon_handle_list_hosts(self.options, self.session, [])
        self.assertEqual(rv, None)
        self.assert_console_message(stdout, expected)
        self.session.listHosts.assert_called_once_with()
        self.session.getLastHostUpdate.assert_called_once_with(list_hosts[0]['id'], ts=True)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_hosts_non_exist_channel(self, stderr):
        channel = 'test-channel'
        expected = "Usage: %s list-hosts [options]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such channel: %s\n" % (self.progname, self.progname, channel)
        self.session.getChannel.return_value = None
        with self.assertRaises(SystemExit) as ex:
            anon_handle_list_hosts(self.options, self.session, ['--channel', channel])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
