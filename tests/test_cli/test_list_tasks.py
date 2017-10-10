import mock
import unittest

import koji
from koji_cli.lib import _list_tasks

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
        }, {'order' : 'priority,create_time'})

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
        }, {'order' : 'priority,create_time'})

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
        }, {'order' : 'priority,create_time'})

        # only method
        session.listTasks.reset_mock()
        options.arch = None
        options.method = 'method'
        _list_tasks(options, session)
        session.listTasks.assert_called_once_with({
            'state': [koji.TASK_STATES[s] for s in ('FREE', 'OPEN', 'ASSIGNED')],
            'decode': True,
            'method': 'method',
        }, {'order' : 'priority,create_time'})

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
        }, {'order' : 'priority,create_time'})
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
        }, {'order' : 'priority,create_time'})
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
                        'children': [ {'id': 3, 'parent': 2, 'sub': True}],
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

