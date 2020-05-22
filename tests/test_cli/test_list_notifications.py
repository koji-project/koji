from __future__ import absolute_import
import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest
from six.moves import StringIO

import koji

from koji_cli.commands import anon_handle_list_notifications

class TestListNotifications(unittest.TestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_list_notifications(self, activate_session_mock, stdout):
        self.session.getBuildNotifications.return_value = [
            {'id': 1, 'tag_id': 1, 'package_id': 11, 'email': 'email@test.com', 'success_only': True},
            {'id': 2, 'tag_id': None, 'package_id': 11, 'email': 'email@test.com', 'success_only': False},
            {'id': 3, 'tag_id': 1, 'package_id': None, 'email': 'email@test.com', 'success_only': True},
        ]
        self.session.getBuildNotificationBlocks.return_value = []
        self.session.getTag.return_value = {'id': 1, 'name': 'tag'}
        self.session.getPackage.return_value = {'id': 11, 'name': 'package'}

        anon_handle_list_notifications(self.options, self.session, ['--mine'])

        actual = stdout.getvalue()
        expected =  '''\
Notifications
    ID Tag                       Package                   E-mail               Success-only
--------------------------------------------------------------------------------------------
     1 tag                       package                   email@test.com       yes         
     2 *                         package                   email@test.com       no          
     3 tag                       *                         email@test.com       yes         

No notification blocks
'''

        self.maxDiff=None
        self.assertMultiLineEqual(actual, expected)
        activate_session_mock.assert_called_once()
        self.session.getTag.assert_has_calls([mock.call(1), mock.call(1)])
        self.session.getPackage.assert_has_calls([mock.call(11), mock.call(11)])
        self.session.getUser.assert_not_called()
        self.session.getBuildNotifications.assert_called_once_with(None)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_list_notifications_user(self, ensure_connection_mock, stdout):
        self.session.getBuildNotifications.return_value = [
            {'id': 1, 'tag_id': 1, 'package_id': 11, 'email': 'email@test.com', 'success_only': True},
            {'id': 2, 'tag_id': None, 'package_id': 11, 'email': 'email@test.com', 'success_only': False},
            {'id': 3, 'tag_id': 1, 'package_id': None, 'email': 'email@test.com', 'success_only': True},
        ]
        self.session.getBuildNotificationBlocks.return_value = [
            {'id': 11, 'tag_id': None, 'package_id': 22},
            {'id': 12, 'tag_id': None, 'package_id': None},
        ]
        self.session.getTag.side_effect = [
            {'id': 1, 'name': 'tag'},
            {'id': 3, 'name': 'tag3'},
        ]
        self.session.getPackage.side_effect = [
            {'id': 11, 'name': 'package'},
            {'id': 11, 'name': 'package'},
            {'id': 22, 'name': 'package'},
        ]
        self.session.getUser.return_value = {'id': 321}

        anon_handle_list_notifications(self.options, self.session, ['--user', 'random_name'])

        actual = stdout.getvalue()
        expected =  '''\
Notifications
    ID Tag                       Package                   E-mail               Success-only
--------------------------------------------------------------------------------------------
     1 tag                       package                   email@test.com       yes         
     2 *                         package                   email@test.com       no          
     3 tag3                      *                         email@test.com       yes         

Notification blocks
    ID Tag                       Package                  
----------------------------------------------------------
    11 *                         package                  
    12 *                         *                        
'''

        self.maxDiff=None
        self.assertMultiLineEqual(actual, expected)
        ensure_connection_mock.assert_called_once_with(self.session)
        self.session.getTag.assert_has_calls([mock.call(1), mock.call(1)])
        self.session.getPackage.assert_has_calls([mock.call(11), mock.call(11)])
        self.session.getUser.assert_called_once_with('random_name')
        self.session.getBuildNotifications.assert_called_once_with(321)

    @mock.patch('sys.exit')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_list_notifications_missing_params(self, sys_stderr, sys_exit):
        sys_exit.side_effect = SystemExit()

        with self.assertRaises(SystemExit):
            anon_handle_list_notifications(self.options, self.session, [])

        self.session.getUser.assert_not_called()
        self.session.getBuildNotifications.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.getPackage.assert_not_called()


    @mock.patch('sys.exit')
    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_handle_list_notifications_no_args(self, sys_stderr, sys_exit):
        sys_exit.side_effect = SystemExit()

        with self.assertRaises(SystemExit):
            anon_handle_list_notifications(self.options, self.session, [])

        self.session.getBuildNotifications.assert_not_called()
