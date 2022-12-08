import mock
import unittest

import koji
import kojihub

QP = kojihub.QueryProcessor
IP = kojihub.InsertProcessor
UP = kojihub.UpdateProcessor


class TestGetNotificationRecipients(unittest.TestCase):
    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        self.queries.append(query)
        return query

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context.opts = {
            'EmailDomain': 'test.domain.com',
            'NotifyOnSuccess': True,
        }

        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.readPackageList = mock.patch('kojihub.kojihub.readPackageList').start()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()

        self.exports = kojihub.RootExports()

    def tearDown(self):
        mock.patch.stopall()

    def test_get_notification_recipients_watchers(self):
        # without build / tag_id
        build = None
        tag_id = None
        state = koji.BUILD_STATES['CANCELED']

        emails = kojihub.get_notification_recipients(build, tag_id, state)
        self.assertEqual(emails, [])

        # only query to watchers
        self.assertEqual(len(self.queries), 1)
        q = self.queries[0]
        self.assertEqual(q.columns, ['email', 'user_id'])
        self.assertEqual(q.tables, ['build_notifications'])
        self.assertEqual(q.clauses, ['package_id IS NULL',
                                     'status = %(users_status)i',
                                     'success_only = FALSE',
                                     'tag_id IS NULL',
                                     'usertype IN %(users_usertypes)s'])
        self.assertEqual(q.joins, ['JOIN users ON build_notifications.user_id = users.id'])
        self.assertEqual(q.values['state'], state)
        self.assertEqual(q.values['build'], build)
        self.assertEqual(q.values['tag_id'], tag_id)

        '''
        q = self.queries[1]
        self.assertEqual(q.columns, ['user_id'])
        self.assertEqual(q.tables, ['build_notifications_block'])
        self.assertEqual(q.clauses, ['user_id IN %(user_ids)s'])
        self.assertEqual(q.joins, [])
        self.assertEqual(q.values['user_ids'], None)
        '''
        self.readPackageList.assert_not_called()

    def test_get_notification_recipients_build_without_tag(self):
        ### with build without tag
        tag_id = None
        state = koji.BUILD_STATES['CANCELED']
        build = {'package_id': 12345, 'owner_name': 'owner_name', 'owner_id': 5}
        self.queries = []
        self.set_queries([
            [{'user_id': 5, 'email': 'owner_name@%s' % self.context.opts['EmailDomain']}],
            []
        ])

        emails = kojihub.get_notification_recipients(build, tag_id, state)
        self.assertEqual(emails, ['owner_name@test.domain.com'])

        # there should be only query to watchers
        self.assertEqual(len(self.queries), 2)
        q = self.queries[0]
        self.assertEqual(q.columns, ['email', 'user_id'])
        self.assertEqual(q.tables, ['build_notifications'])
        self.assertEqual(q.clauses, ['package_id = %(package_id)i OR package_id IS NULL',
                                     'status = %(users_status)i',
                                     'success_only = FALSE',
                                     'tag_id IS NULL',
                                     'usertype IN %(users_usertypes)s'])
        self.assertEqual(q.joins, ['JOIN users ON build_notifications.user_id = users.id'])
        self.assertEqual(q.values['package_id'], build['package_id'])
        self.assertEqual(q.values['state'], state)
        self.assertEqual(q.values['build'], build)
        self.assertEqual(q.values['tag_id'], tag_id)

        q = self.queries[1]
        self.assertEqual(q.columns, ['user_id'])
        self.assertEqual(q.tables, ['build_notifications_block'])
        self.assertEqual(q.clauses, ['package_id = %(package_id)i OR package_id IS NULL',
                                     'tag_id IS NULL',
                                     'user_id IN %(user_ids)s',
                                     ])
        self.assertEqual(q.joins, None)
        self.assertEqual(q.values['user_ids'], [5])

        self.readPackageList.assert_not_called()

    def test_get_notification_recipients_tag_without_build(self):
        ### with tag without build makes no sense
        build = None
        tag_id = 123
        state = koji.BUILD_STATES['CANCELED']
        self.queries = []

        with self.assertRaises(koji.GenericError):
            kojihub.get_notification_recipients(build, tag_id, state)
        self.assertEqual(self.queries, [])
        self.readPackageList.assert_not_called()

    def set_queries(self, return_values):
        self.query_returns = return_values
        self.query_returns.reverse()

        def getQuery(*args, **kwargs):
            q = QP(*args, **kwargs)
            q.execute = mock.MagicMock()
            q.execute.return_value = self.query_returns.pop()
            self.queries.append(q)
            return q
        self.QueryProcessor.side_effect = getQuery

    def test_get_notification_recipients_tag_with_build(self):
        ### with tag and build
        build = {'package_id': 12345, 'owner_name': 'owner_name', 'owner_id': 5}
        tag_id = 123
        state = koji.BUILD_STATES['CANCELED']
        self.readPackageList.return_value = {12345: {'blocked': False, 'owner_id': 'owner_id'}}
        self.get_user.return_value = {
            'id': 342,
            'name': 'pkg_owner_name',
            'status': koji.USER_STATUS['NORMAL'],
            'usertype': koji.USERTYPES['NORMAL']
        }
        self.set_queries([
            [{'user_id': 5, 'email': 'owner_name@%s' % self.context.opts['EmailDomain']}],
            []
        ])

        emails = kojihub.get_notification_recipients(build, tag_id, state)
        self.assertEqual(sorted(emails),
                         ['owner_name@test.domain.com', 'pkg_owner_name@test.domain.com'])

        # there should be only query to watchers
        self.assertEqual(len(self.queries), 2)
        q = self.queries[0]
        self.assertEqual(q.columns, ['email', 'user_id'])
        self.assertEqual(q.tables, ['build_notifications'])
        self.assertEqual(q.clauses, ['package_id = %(package_id)i OR package_id IS NULL',
                                     'status = %(users_status)i',
                                     'success_only = FALSE',
                                     'tag_id = %(tag_id)i OR tag_id IS NULL',
                                     'usertype IN %(users_usertypes)s',
                                     ])
        self.assertEqual(q.joins, ['JOIN users ON build_notifications.user_id = users.id'])
        self.assertEqual(q.values['package_id'], build['package_id'])
        self.assertEqual(q.values['state'], state)
        self.assertEqual(q.values['build'], build)
        self.assertEqual(q.values['tag_id'], tag_id)

        q = self.queries[1]
        self.assertEqual(q.columns, ['user_id'])
        self.assertEqual(q.tables, ['build_notifications_block'])
        self.assertEqual(q.clauses, ['package_id = %(package_id)i OR package_id IS NULL',
                                     'tag_id = %(tag_id)i OR tag_id IS NULL',
                                     'user_id IN %(user_ids)s',
                                     ])
        self.assertEqual(q.joins, None)
        self.assertEqual(sorted(q.values['user_ids']), [5, 342])
        self.readPackageList.assert_called_once_with(
            pkgID=build['package_id'], tagID=tag_id, inherit=True)
        self.get_user.asssert_called_once_with(342, strict=True)

    def test_get_notification_recipients_blocked_pkg_owner(self):
        # blocked package owner
        build = {'package_id': 12345, 'owner_name': 'owner_name', 'owner_id': 5}
        tag_id = 123
        state = koji.BUILD_STATES['CANCELED']
        self.get_user.return_value = {
            'id': 342,
            'name': 'pkg_owner_name',
            'status': koji.USER_STATUS['BLOCKED'],
            'usertype': koji.USERTYPES['NORMAL']
        }
        self.set_queries([
            [{'user_id': 5, 'email': 'owner_name@%s' % self.context.opts['EmailDomain']}],
            []
        ])
        emails = kojihub.get_notification_recipients(build, tag_id, state)
        self.assertEqual(emails, ['owner_name@test.domain.com'])

    def test_get_notification_recipients_optout(self):
        # blocked package owner
        build = {'package_id': 12345, 'owner_name': 'owner_name', 'owner_id': 5}
        tag_id = 123
        state = koji.BUILD_STATES['CANCELED']
        self.get_user.return_value = {
            'id': 342,
            'name': 'pkg_owner_name',
            'status': koji.USER_STATUS['NORMAL'],
            'usertype': koji.USERTYPES['NORMAL']
        }
        self.set_queries([
            [{'user_id': 5, 'email': 'owner_name@%s' % self.context.opts['EmailDomain']}],
            [{'user_id': 5}]
        ])
        emails = kojihub.get_notification_recipients(build, tag_id, state)
        self.assertEqual(emails, [])

    def test_get_notification_recipients_machine(self):
        # package owner is machine
        build = {'package_id': 12345, 'owner_name': 'owner_name', 'owner_id': 5}
        tag_id = 123
        state = koji.BUILD_STATES['CANCELED']
        self.get_user.return_value = {
            'id': 342,
            'name': 'pkg_owner_name',
            'status': koji.USER_STATUS['NORMAL'],
            'usertype': koji.USERTYPES['HOST']
        }
        self.set_queries([
            [{'user_id': 5, 'email': 'owner_name@%s' % self.context.opts['EmailDomain']}],
            []
        ])
        emails = kojihub.get_notification_recipients(build, tag_id, state)
        self.assertEqual(emails, ['owner_name@test.domain.com'])
