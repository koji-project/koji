from __future__ import absolute_import
import mock
import six
import unittest

import koji
from koji_cli.commands import handle_restart_hosts
from . import utils


class TestRestartHosts(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.options = mock.MagicMock()
        self.options.quiet = None
        self.options.poll_interval = 3
        self.session = mock.MagicMock()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.running_in_bg_mock = mock.patch('koji_cli.commands._running_in_bg').start()
        self.running_in_bg_mock.return_value = False
        self.watch_tasks_mock = mock.patch('koji_cli.commands.watch_tasks').start()
        self.task_id = 101

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_restart_hosts_force_options(self):
        """Test %s function with --force option""" % handle_restart_hosts.__name__
        arguments = ['--force']

        self.session.getHost.return_value = None
        self.session.restartHosts.return_value = self.task_id
        self.session.logout.return_value = None

        # has other restart tasks are running case
        self.session.listTasks.return_value = [{'id': 1}, {'id': 2}, {'id': 3}]

        handle_restart_hosts(self.options, self.session, arguments)
        self.activate_session_mock.assert_called_once()
        self.session.listTasks.assert_not_called()

        self.session.restartHosts.assert_called_with()
        self.session.logout.assert_called_once()
        self.watch_tasks_mock.assert_called_with(
            self.session, [self.task_id], quiet=None, poll_interval=3, topurl=self.options.topurl)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    def test_handle_restart_hosts_has_other_tasks(self, stderr):
        """Test %s function when there has other restart tasks exist
        """ % handle_restart_hosts.__name__

        self.session.getHost.return_value = None
        self.session.restartHosts.return_value = True
        self.session.logout.return_value = None

        #
        # session.listTasks returns:
        #
        # [{'weight': 0.1,
        #   'awaited': None,
        #   'completion_time': None,
        #   'create_time': '2017-11-02 18:30:08.933753',
        #   'result': None,
        #   'owner': 1,
        #   'id': 11,
        #   'state': 1,
        #   'label': None,
        #   'priority': 5,
        #   'waiting': True,
        #   'completion_ts': None,
        #   'method': 'restartHosts',
        #   'owner_name': 'kojiadmin',
        #   'parent': None,
        #   'start_time': '2017-11-02 18:30:28.028843',
        #   'start_ts': 1509647428.02884,
        #   'create_ts': 1509647408.93375,
        #   'host_id': 1, 'arch': 'noarch',
        #   'request': "<?xml version='1.0'?>\n<methodCall>\n<methodName>restartHosts</methodName>
        #   \n<params>\n</params>\n</methodCall>\n",
        #   'channel_id': 1,
        #   'owner_type': 0}]
        #

        # has other restart tasks are running case
        self.session.listTasks.return_value = [{'id': 1}, {'id': 2}, {'id': 3}]

        with self.assertRaises(SystemExit) as ex:
            handle_restart_hosts(self.options, self.session, [])
        self.assertExitCode(ex, 1)
        self.activate_session_mock.assert_called_once()

        query_opt = {
            'method': 'restartHosts',
            'state': [koji.TASK_STATES[s] for s in ('FREE', 'OPEN', 'ASSIGNED')]
        }

        self.session.listTasks.assert_called_with(query_opt)
        self.session.restartHosts.assert_not_called()
        self.session.logout.assert_not_called()

        expect = "Found other restartHosts tasks running.\n"
        expect += "Task ids: %r\n" % \
            [t['id'] for t in self.session.listTasks.return_value]
        expect += "Use --force to run anyway\n"
        self.assert_console_message(stderr, expect)

    @mock.patch('koji_cli.commands._running_in_bg')
    def test_handle_restart_hosts_wait_option(self, running_in_bg_mock):
        """Test %s function with --force option""" % handle_restart_hosts.__name__
        arguments = ['--wait']

        # --wait is specified, running_in_bg() should not matter.
        running_in_bg_mock.return_value = True

        self.session.getHost.return_value = None
        self.session.restartHosts.return_value = self.task_id
        self.session.logout.return_value = None

        # has other restart tasks are running case
        self.session.listTasks.return_value = []

        handle_restart_hosts(self.options, self.session, arguments)
        self.activate_session_mock.assert_called_once()
        self.session.listTasks.assert_called_once()

        self.session.restartHosts.assert_called_with()
        self.session.logout.assert_called_once()
        self.watch_tasks_mock.assert_called_with(
            self.session, [self.task_id], quiet=None, poll_interval=3, topurl=self.options.topurl)

    @mock.patch('koji_cli.commands._running_in_bg')
    def test_handle_restart_hosts_other_options(self, running_in_bg_mock):
        """Test %s function with --force option""" % handle_restart_hosts.__name__
        arguments = ['--nowait',
                     '--channel', 'createrepo',
                     '--arch', 'x86_64',
                     '--timeout', '10']

        # --no-wait is specified, running_in_bg() should not matter.
        running_in_bg_mock.return_value = True

        self.session.getHost.return_value = None
        self.session.restartHosts.return_value = 101
        self.session.logout.return_value = None

        # has other restart tasks are running case
        self.session.listTasks.return_value = []

        handle_restart_hosts(self.options, self.session, arguments)
        self.activate_session_mock.assert_called_once()
        self.session.listTasks.assert_called_once()

        self.session.restartHosts.assert_called_with(
            options={'arches': ['x86_64'], 'timeout': 10, 'channel': 'createrepo'})
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands._running_in_bg')
    def test_handle_restart_hosts_arguments(self, running_in_bg_mock, stderr):
        """Test %s function with --force option""" % handle_restart_hosts.__name__

        # --no-wait is specified, running_in_bg() should not matter.
        running_in_bg_mock.return_value = True

        with self.assertRaises(SystemExit) as ex:
            handle_restart_hosts(self.options, self.session, ['10'])

        self.assertExitCode(ex, 2)
        expected_msg = """Usage: %s restart-hosts [options]
(Specify the --help global option for a list of other help options)

%s: error: restart-hosts does not accept arguments
""" % (self.progname, self.progname)
        self.assert_console_message(stderr, expected_msg)

        self.session.listTasks.assert_not_called()
        self.activate_session_mock.assert_not_called()
        self.session.restartHosts.assert_not_called()
        self.session.logout.assert_not_called()
        self.watch_tasks_mock.assert_not_called()

    def test_handle_restart_hosts_help(self):
        self.assert_help(
            handle_restart_hosts,
            """Usage: %s restart-hosts [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --wait                Wait on the task, even if running in the background
  --nowait              Don't wait on task
  --quiet               Do not print the task information
  --force               Ignore checks and force operation
  --channel=CHANNEL     Only hosts in this channel
  -a ARCH, --arch=ARCH  Limit to hosts of this architecture (can be given
                        multiple times)
  --timeout=N           Time out after N seconds
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
