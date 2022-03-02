from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_list_notifications
from . import utils


class TestListNotifications(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.ensure_connection_mock = mock.patch('koji_cli.commands.ensure_connection').start()
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s list-notifications [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_notifications(self, stdout):
        self.session.getBuildNotifications.return_value = [
            {'id': 1, 'tag_id': 1, 'package_id': 11, 'email': 'email@test.com',
             'success_only': True},
            {'id': 2, 'tag_id': None, 'package_id': 11, 'email': 'email@test.com',
             'success_only': False},
            {'id': 3, 'tag_id': 1, 'package_id': None, 'email': 'email@test.com',
             'success_only': True},
        ]
        self.session.getBuildNotificationBlocks.return_value = []
        self.session.getTag.return_value = {'id': 1, 'name': 'tag'}
        self.session.getPackage.return_value = {'id': 11, 'name': 'package'}

        anon_handle_list_notifications(self.options, self.session, ['--mine'])

        actual = stdout.getvalue()
        expected = '''\
Notifications
    ID Tag                       Package                   E-mail               Success-only
--------------------------------------------------------------------------------------------
     1 tag                       package                   email@test.com       yes         
     2 *                         package                   email@test.com       no          
     3 tag                       *                         email@test.com       yes         

No notification blocks
'''

        self.assertMultiLineEqual(actual, expected)
        self.session.getTag.assert_has_calls([mock.call(1), mock.call(1)])
        self.session.getPackage.assert_has_calls([mock.call(11), mock.call(11)])
        self.session.getUser.assert_not_called()
        self.session.getBuildNotifications.assert_called_once_with(None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.ensure_connection_mock.asset_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_notifications_user(self, stdout):
        self.session.getBuildNotifications.return_value = [
            {'id': 1, 'tag_id': 1, 'package_id': 11, 'email': 'email@test.com',
             'success_only': True},
            {'id': 2, 'tag_id': None, 'package_id': 11, 'email': 'email@test.com',
             'success_only': False},
            {'id': 3, 'tag_id': 1, 'package_id': None, 'email': 'email@test.com',
             'success_only': True},
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
        expected = '''\
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

        self.assertMultiLineEqual(actual, expected)
        self.session.getTag.assert_has_calls([mock.call(1), mock.call(1)])
        self.session.getPackage.assert_has_calls([mock.call(11), mock.call(11)])
        self.session.getUser.assert_called_once_with('random_name')
        self.session.getBuildNotifications.assert_called_once_with(321)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.activate_session_mock.asset_not_called()

    def test_handle_list_notifications_without_option(self):
        self.assert_system_exit(
            anon_handle_list_notifications,
            self.options, self.session, [],
            stderr=self.format_error_message('Use --user or --mine.'),
            exit_code=2,
            activate_session=None)
        self.session.getBuildNotifications.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.getPackage.assert_not_called()
        self.session.getUser.assert_not_called()
        self.ensure_connection_mock.asset_not_called()
        self.activate_session_mock.asset_not_called()

    def test_handle_list_notifications_with_args(self):
        self.assert_system_exit(
            anon_handle_list_notifications,
            self.options, self.session, ['test-argument'],
            stderr=self.format_error_message('This command takes no arguments'),
            exit_code=2,
            activate_session=None)
        self.session.getBuildNotifications.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.getPackage.assert_not_called()
        self.session.getUser.assert_not_called()
        self.ensure_connection_mock.asset_not_called()
        self.activate_session_mock.asset_not_called()

    def test_list_notifications_user_non_exist_user(self):
        username = 'random_name'
        self.session.getUser.return_value = None
        self.assert_system_exit(
            anon_handle_list_notifications,
            self.options, self.session, ['--user', username],
            stderr='No such user: %s\n' % username,
            exit_code=1,
            activate_session=None)
        self.session.getBuildNotifications.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.getPackage.assert_not_called()
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.activate_session_mock.asset_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_notifications_without_notification(self, stdout):
        username = 'random_name'
        self.session.getUser.return_value = {'id': 321}
        self.session.getBuildNotifications.return_value = []
        self.session.getBuildNotificationBlocks.return_value = [
            {'id': 11, 'tag_id': 22, 'package_id': None}
        ]
        self.session.getTag.return_value = {'id': 22, 'name': 'tag'}
        anon_handle_list_notifications(self.options, self.session, ['--user', username])
        expected = """No notifications

Notification blocks
    ID Tag                       Package                  
----------------------------------------------------------
    11 tag                       *                        
"""
        actual = stdout.getvalue()
        self.assertMultiLineEqual(actual, expected)
        self.session.getTag.assert_called_once_with(22)
        self.session.getPackage.assert_not_called()
        self.session.getUser.assert_called_once_with('random_name')
        self.session.getBuildNotifications.assert_called_once_with(321)
        self.ensure_connection_mock.assert_called_once_with(self.session, self.options)
        self.activate_session_mock.asset_not_called()
