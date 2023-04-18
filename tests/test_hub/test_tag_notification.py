import mock

import unittest
import kojihub
import kojihub.kojihub


class TestTagNotification(unittest.TestCase):
    def setUp(self):
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.get_tag = mock.patch('kojihub.kojihub.get_tag').start()
        self.get_notification_recipients = mock.patch(
            'kojihub.kojihub.get_notification_recipients').start()
        self.make_task = mock.patch('kojihub.kojihub.make_task').start()
        self.build_info = {'state': 0, 'id': 3}
        self.tag_id = 1
        self.from_id = 2

    def tearDown(self):
        mock.patch.stopall()

    def test_disabled_notification(self):
        is_successful = True
        tag_id = 1
        from_id = 2
        user_id = 4
        self.context.opts = {'DisableNotifications': True}
        rv = kojihub.tag_notification(is_successful, tag_id, from_id, self.build_info['id'],
                                      user_id, ignore_success=False, failure_msg='')
        self.assertEqual(rv, None)
        self.get_build.assert_not_called()
        self.get_user.assert_not_called()
        self.get_tag.assert_not_called()
        self.get_notification_recipients.assert_not_called()
        self.make_task.assert_not_called()

    def test_build_not_exists(self):
        is_successful = True
        user_id = 4
        self.get_build.return_value = None
        self.context.opts = {'DisableNotifications': False}
        rv = kojihub.tag_notification(is_successful, self.tag_id, self.from_id,
                                      self.build_info['id'], user_id, ignore_success=False,
                                      failure_msg='')
        self.assertEqual(rv, None)
        self.get_build.assert_called_once_with(self.build_info['id'])
        self.get_user.assert_not_called()
        self.get_tag.assert_not_called()
        self.get_notification_recipients.assert_not_called()
        self.make_task.assert_not_called()

    def test_valid_make_task(self):
        is_successful = False
        user_id = 'testuser'
        userinfo = {'id': 4}
        recipients_uniq = ['email1@mail.com', 'email2@mail.com', 'email3@mail.com']
        self.get_build.return_value = self.build_info
        self.get_user.return_value = userinfo
        self.get_tag.side_effect = [{'id': self.tag_id}, {'id': self.from_id}]
        self.get_notification_recipients.side_effect = [['email1@mail.com', 'email2@mail.com'],
                                                        ['email3@mail.com', 'email1@mail.com']]
        self.make_task.return_value = 10
        self.context.opts = {'DisableNotifications': False}
        rv = kojihub.tag_notification(is_successful, self.tag_id, self.from_id,
                                      self.build_info['id'], user_id, ignore_success=False,
                                      failure_msg='')
        self.assertEqual(rv, 10)
        self.get_build.assert_called_once_with(self.build_info['id'])
        self.get_user.assert_called_once_with(user_id, strict=True)
        self.get_tag.assert_has_calls([mock.call(self.tag_id), mock.call(self.from_id)])
        self.get_notification_recipients.assert_has_calls(
            [mock.call(self.build_info, self.tag_id, 3),
             mock.call(self.build_info, self.from_id, 3)])
        self.make_task.assert_called_once_with('tagNotification',
                                               [recipients_uniq, is_successful, self.tag_id,
                                                self.from_id, self.build_info['id'],
                                                userinfo['id'], False, ''])

    def test_valid_without_make_task(self):
        is_successful = True
        user_id = 'testuser'
        self.get_build.return_value = self.build_info
        self.get_user.return_value = {'id': 4}
        self.get_tag.side_effect = [{'id': self.tag_id}, {'id': self.from_id}]
        self.get_notification_recipients.side_effect = [['email1@mail.com', 'email2@mail.com'],
                                                        ['email3@mail.com', 'email4@mail.com']]
        self.context.opts = {'DisableNotifications': False}
        rv = kojihub.tag_notification(is_successful, self.tag_id, self.from_id,
                                      self.build_info['id'], user_id, ignore_success=True,
                                      failure_msg='')
        self.assertEqual(rv, None)
        self.get_build.assert_called_once_with(self.build_info['id'])
        self.get_user.assert_called_once_with(user_id, strict=True)
        self.get_tag.assert_has_calls([mock.call(self.tag_id), mock.call(self.from_id)])
        self.get_notification_recipients.assert_has_calls(
            [mock.call(self.build_info, self.tag_id, 1),
             mock.call(self.build_info, self.from_id, 1)])
        self.make_task.assert_not_called()
