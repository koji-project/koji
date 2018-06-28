from __future__ import absolute_import
import mock
import six
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import koji
from koji_cli.lib import _list_tasks
from koji_cli.commands import handle_list_tasks
from . import utils


class TestListTasks(unittest.TestCase):
    def setUp(self):
        pass

    @mock.patch('sys.exit')
    def test_list_tasks(self, sys_exit):
        options = mock.MagicMock(name='options')
        options.mine = True
        options.user = None
        options.arch = None
        options.method = None
        options.channel = None
        options.host = None
        session = mock.MagicMock(name='session')
        session.getLoggedInUser.return_value = {'id': 1, 'username': 'name'}
        session.listTasks.return_value = []
        sys_exit.side_effect = RuntimeError

        # mine
        r = _list_tasks(options, session)
        self.assertEqual(r, [])
        session.listTasks.assert_called_once_with({
            'state': [koji.TASK_STATES[s] for s in ('FREE', 'OPEN', 'ASSIGNED')],
            'decode': True,
            'owner': 1,
        }, {'order': 'priority,create_time'})

        # invalid me
        session.getLoggedInUser.return_value = None
        with self.assertRaises(RuntimeError):
            _list_tasks(options, session)

        # mine + user -> error
        options.user = 2
        with self.assertRaises(koji.GenericError):
            _list_tasks(options, session)

        # only user
        session.listTasks.reset_mock()
        options.mine = None
        session.getUser.return_value = {'id': 2, 'username': 'name'}
        _list_tasks(options, session)
        session.listTasks.assert_called_once_with({
            'state': [koji.TASK_STATES[s] for s in ('FREE', 'OPEN', 'ASSIGNED')],
            'decode': True,
            'owner': 2,
        }, {'order': 'priority,create_time'})

        # invalid user
        session.getUser.return_value = None
        with self.assertRaises(RuntimeError):
            _list_tasks(options, session)

        # only arch
        session.listTasks.reset_mock()
        options.user = None
        options.arch = 'x86_64,i386'
        _list_tasks(options, session)
        session.listTasks.assert_called_once_with({
            'state': [koji.TASK_STATES[s] for s in ('FREE', 'OPEN', 'ASSIGNED')],
            'decode': True,
            'arch': ['x86_64', 'i386'],
        }, {'order': 'priority,create_time'})

        # only method
        session.listTasks.reset_mock()
        options.arch = None
        options.method = 'method'
        _list_tasks(options, session)
        session.listTasks.assert_called_once_with({
            'state': [koji.TASK_STATES[s] for s in ('FREE', 'OPEN', 'ASSIGNED')],
            'decode': True,
            'method': 'method',
        }, {'order': 'priority,create_time'})

        # only channel
        session.listTasks.reset_mock()
        options.method = None
        options.channel = 'channel'
        session.getChannel.return_value = {'id': 123, 'name': 'channel'}
        _list_tasks(options, session)
        session.listTasks.assert_called_once_with({
            'state': [koji.TASK_STATES[s] for s in ('FREE', 'OPEN', 'ASSIGNED')],
            'decode': True,
            'channel_id': 123,
        }, {'order': 'priority,create_time'})
        session.getChannel.assert_called_once_with('channel')

        # invalid channel
        session.getChannel.return_value = None
        with self.assertRaises(RuntimeError):
            _list_tasks(options, session)

        # only host
        session.listTasks.reset_mock()
        options.channel = None
        options.host = 'host'
        session.getHost.return_value = {'id': 234}
        _list_tasks(options, session)
        session.listTasks.assert_called_once_with({
            'state': [koji.TASK_STATES[s] for s in ('FREE', 'OPEN', 'ASSIGNED')],
            'decode': True,
            'host_id': 234,
        }, {'order': 'priority,create_time'})
        session.getHost.assert_called_once_with('host')

        # invalid host
        session.getHost.return_value = None
        with self.assertRaises(RuntimeError):
            _list_tasks(options, session)

        # parent/children threading
        options.host = None
        session.listTasks.return_value = [
            {'id': 1, 'parent': None},
            {'id': 2, 'parent': 1},
            {'id': 3, 'parent': 2},
        ]
        r = _list_tasks(options, session)
        self.assertEqual(r, [
            {
                'children': [
                    {
                        'children': [{'id': 3, 'parent': 2, 'sub': True}],
                        'id': 2,
                        'parent': 1,
                        'sub': True
                    }
                ],
                'id': 1,
                'parent': None
            },
            {
                'children': [{'id': 3, 'parent': 2, 'sub': True}],
                'id': 2,
                'parent': 1,
                'sub': True
            },
            {
                'id': 3,
                'parent': 2,
                'sub': True}
            ])


class TestCliListTasks(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s list-tasks [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands._list_tasks')
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_list_tasks(
            self,
            activate_session_mock,
            list_tasks_mock,
            stdout):
        """Test handle_list_tasks function"""
        session = mock.MagicMock()
        options = mock.MagicMock(quiet=False)

        tasks = [
            {
                'id': 5,
                'sub': True,
                'state': 0,
                'owner_name': 'kojiadmin',
                'method': 'createrepo',
                'parent': 3,
                'priority': 14,
                'arch': 'noarch'
            },
            {
                'children':
                [
                    {
                        'id': 5,
                        'sub': True,
                        'state': 0,
                        'owner_name': 'kojiadmin',
                        'method': 'createrepo',
                        'parent': 3,
                        'priority': 14,
                        'arch': 'noarch'
                    },
                ],
                'id': 3,
                'state': 0,
                'owner_name': 'kojiadmin',
                'method': 'newRepo',
                'priority': 15,
                'arch': 'noarch',
            }
        ]

        header = \
            "ID       Pri  Owner                State    Arch       Name\n"
        task_output = \
            "3        15   kojiadmin            FREE     noarch     newRepo (noarch)\n" + \
            "5        14   kojiadmin            FREE     noarch      +createrepo (noarch)\n"

        expected = self.format_error_message(
            "This command takes no arguments")

        # Case 1, argument error test.
        self.assert_system_exit(
            handle_list_tasks,
            options,
            session,
            ['test'],
            stderr=expected,
            activate_session=None)

        # Case 2, no tasks
        list_tasks_mock.return_value = None
        handle_list_tasks(options, session, [])
        self.assert_console_message(stdout, '(no tasks)\n')

        # Case 3, show tasks with header
        list_tasks_mock.return_value = tasks
        handle_list_tasks(options, session, [])
        self.assert_console_message(stdout, header + task_output)

        # Case 4. show task without header
        handle_list_tasks(options, session, ['--quiet'])
        self.assert_console_message(stdout, task_output)

    def test_handle_list_tasks_help(self):
        self.assert_help(
            handle_list_tasks,
            """Usage: %s list-tasks [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help         show this help message and exit
  --mine             Just print your tasks
  --user=USER        Only tasks for this user
  --arch=ARCH        Only tasks for this architecture
  --method=METHOD    Only tasks of this method
  --channel=CHANNEL  Only tasks in this channel
  --host=HOST        Only tasks for this host
  --quiet            Do not display the column headers
""" % self.progname)
