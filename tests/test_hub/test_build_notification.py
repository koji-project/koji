from unittest import mock

import koji
import unittest
import kojihub
import kojihub.kojihub
from .utils import DBQueryTestCase


class TestBuildNotification(unittest.TestCase):
    def setUp(self):
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.session.assertPerm = mock.MagicMock()
        self.get_build = mock.patch('kojihub.kojihub.get_build').start()
        self._get_build_target = mock.patch('kojihub.kojihub._get_build_target').start()
        self.get_notification_recipients = mock.patch(
            'kojihub.kojihub.get_notification_recipients').start()
        self.make_task = mock.patch('kojihub.kojihub.make_task').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_disabled_notification(self):
        self.context.opts = {'DisableNotifications': True}
        rv = kojihub.build_notification(10, 1)
        self.assertEqual(rv, None)
        self.get_build.assert_not_called()
        self._get_build_target.assert_not_called()
        self.get_notification_recipients.assert_not_called()
        self.make_task.assert_not_called()

    def test_not_complete_build(self):
        build_id = 1
        task_id = 10
        self.context.opts = {'DisableNotifications': False}
        buildinfo = {'state': 0, 'id': build_id}
        target_info = {'dest_tag': 'test_dest_tag'}
        self.get_build.return_value = buildinfo
        self._get_build_target.return_value = target_info

        with self.assertRaises(koji.GenericError) as ex:
            kojihub.build_notification(task_id, build_id)
        self.assertEqual('never send notifications for incomplete builds', str(ex.exception))
        self.get_build.assert_called_once_with(build_id)
        self._get_build_target.assert_called_once_with(task_id)
        self.get_notification_recipients.assert_not_called()
        self.make_task.assert_not_called()

    def test_valid(self):
        build_id = 1
        task_id = 10
        self.context.opts = {'DisableNotifications': False}
        buildinfo = {'state': 1, 'id': build_id}
        target_info = {'dest_tag': 'test_dest_tag'}
        recipients = ['email1@mail.com', 'email2@mail.com']
        weburl = 'http://localhost/koji'
        self.get_build.return_value = buildinfo
        self._get_build_target.return_value = target_info
        self.get_notification_recipients.return_value = recipients
        self.make_task.return_value = 11

        rv = kojihub.build_notification(task_id, build_id)
        self.assertEqual(rv, None)
        self.get_build.assert_called_once_with(build_id)
        self._get_build_target.assert_called_once_with(task_id)
        self.get_notification_recipients.assert_called_once_with(
            buildinfo, target_info['dest_tag'], buildinfo['state'])
        self.make_task.assert_called_once_with('buildNotification',
                                               [recipients, buildinfo, target_info, weburl])


class TestGetBuildNotifications(DBQueryTestCase):
    def setUp(self):
        super(TestGetBuildNotifications, self).setUp()

    def tearDown(self):
        mock.patch.stopall()

    def test_valid(self):
        user_id = 1
        kojihub.get_build_notifications(user_id)
        self.assertEqual(len(self.queries), 1)
        self.assertLastQueryEqual(tables=['build_notifications'],
                                  columns=['email', 'id', 'package_id', 'success_only', 'tag_id',
                                           'user_id'],
                                  clauses=['user_id = %(user_id)i'],
                                  values={'user_id': user_id})


class TestGetBuildNotificationBlocks(DBQueryTestCase):
    def setUp(self):
        super(TestGetBuildNotificationBlocks, self).setUp()

    def tearDown(self):
        mock.patch.stopall()

    def test_valid(self):
        user_id = 1
        kojihub.get_build_notification_blocks(user_id)
        self.assertEqual(len(self.queries), 1)
        self.assertLastQueryEqual(tables=['build_notifications_block'],
                                  columns=['id', 'package_id', 'tag_id', 'user_id'],
                                  clauses=['user_id = %(user_id)i'],
                                  values={'user_id': user_id})
