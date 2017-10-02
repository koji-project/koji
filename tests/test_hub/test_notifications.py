import mock
import unittest

import koji
import kojihub

QP = kojihub.QueryProcessor

class TestGetNotificationRecipients(unittest.TestCase):
    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        self.queries.append(query)
        return query

    def setUp(self):
        self.context = mock.patch('kojihub.context').start()
        self.context.opts = {
            'EmailDomain': 'test.domain.com',
            'NotifyOnSuccess': True,
        }

        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                side_effect=self.getQuery).start()
        self.queries = []

    def tearDown(self):
        mock.patch.stopall()


    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub.readPackageList')
    def test_get_notification_recipients(self, readPackageList, get_user):
        # without build / tag_id
        build = None
        tag_id = None
        state = koji.BUILD_STATES['CANCELED']

        emails = kojihub.get_notification_recipients(build, tag_id, state)
        self.assertEqual(emails, set([]))

        # only query to watchers
        self.assertEqual(len(self.queries), 1)
        q = self.queries[0]
        self.assertEqual(q.columns, ('email',))
        self.assertEqual(q.tables, ['build_notifications', 'users'])
        self.assertEqual(q.clauses, ['users.id = build_notifications.user_id',
                                     'users.status = 0',
                                     'users.usertype = 0',
                                     'package_id IS NULL',
                                     'tag_id IS NULL',
                                     'success_only = FALSE'])
        self.assertEqual(q.values['state'], state)
        self.assertEqual(q.values['build'], build)
        self.assertEqual(q.values['tag_id'], tag_id)
        readPackageList.assert_not_called()


        ### with build without tag
        build = {'package_id': 12345, 'owner_name': 'owner_name'}
        self.queries = []

        emails = kojihub.get_notification_recipients(build, tag_id, state)
        self.assertEqual(emails, set(['owner_name@test.domain.com']))

        # there should be only query to watchers
        self.assertEqual(len(self.queries), 1)
        q = self.queries[0]
        self.assertEqual(q.columns, ('email',))
        self.assertEqual(q.tables, ['build_notifications', 'users'])
        self.assertEqual(q.clauses, ['users.id = build_notifications.user_id',
                                     'users.status = 0',
                                     'users.usertype = 0',
                                     'package_id = %(package_id)i OR package_id IS NULL',
                                     'tag_id IS NULL',
                                     'success_only = FALSE'])
        self.assertEqual(q.values['package_id'], build['package_id'])
        self.assertEqual(q.values['state'], state)
        self.assertEqual(q.values['build'], build)
        self.assertEqual(q.values['tag_id'], tag_id)
        readPackageList.assert_not_called()

        ### with tag without build makes no sense
        build = None
        tag_id = 123
        self.queries = []

        with self.assertRaises(koji.GenericError):
            kojihub.get_notification_recipients(build, tag_id, state)
        self.assertEqual(self.queries, [])
        readPackageList.assert_not_called()


        ### with tag and build
        build = {'package_id': 12345, 'owner_name': 'owner_name'}
        tag_id = 123
        self.queries = []
        readPackageList.return_value = {12345: {'blocked': False, 'owner_id': 'owner_id'}}
        get_user.return_value = {
            'id': 'owner_id',
            'name': 'pkg_owner_name',
            'status': koji.USER_STATUS['NORMAL'],
            'usertype': koji.USERTYPES['NORMAL']
        }

        emails = kojihub.get_notification_recipients(build, tag_id, state)
        self.assertEqual(emails, set(['owner_name@test.domain.com', 'pkg_owner_name@test.domain.com']))


        # there should be only query to watchers
        self.assertEqual(len(self.queries), 1)
        q = self.queries[0]
        self.assertEqual(q.columns, ('email',))
        self.assertEqual(q.tables, ['build_notifications', 'users'])
        self.assertEqual(q.clauses, ['users.id = build_notifications.user_id',
                                     'users.status = 0',
                                     'users.usertype = 0',
                                     'package_id = %(package_id)i OR package_id IS NULL',
                                     'tag_id = %(tag_id)i OR tag_id IS NULL',
                                     'success_only = FALSE'])
        self.assertEqual(q.values['package_id'], build['package_id'])
        self.assertEqual(q.values['state'], state)
        self.assertEqual(q.values['build'], build)
        self.assertEqual(q.values['tag_id'], tag_id)
        readPackageList.assert_called_once_with(pkgID=build['package_id'], tagID=tag_id, inherit=True)
        get_user.asssert_called_once_with('owner_id', strict=True)

        # blocked package owner
        get_user.return_value = {
            'id': 'owner_id',
            'name': 'pkg_owner_name',
            'status': koji.USER_STATUS['BLOCKED'],
            'usertype': koji.USERTYPES['NORMAL']
        }
        emails = kojihub.get_notification_recipients(build, tag_id, state)
        self.assertEqual(emails, set(['owner_name@test.domain.com']))

        # package owner is machine
        get_user.return_value = {
            'id': 'owner_id',
            'name': 'pkg_owner_name',
            'status': koji.USER_STATUS['NORMAL'],
            'usertype': koji.USERTYPES['HOST']
        }
        emails = kojihub.get_notification_recipients(build, tag_id, state)
        self.assertEqual(emails, set(['owner_name@test.domain.com']))
