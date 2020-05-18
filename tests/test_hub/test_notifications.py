import mock
import unittest

import koji
import kojihub

QP = kojihub.QueryProcessor
IP = kojihub.InsertProcessor
UP = kojihub.UpdateProcessor

class TestNotifications(unittest.TestCase):
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
        self.context = mock.patch('kojihub.context').start()
        self.context.opts = {
            'EmailDomain': 'test.domain.com',
            'NotifyOnSuccess': True,
        }

        self.QueryProcessor = mock.patch('kojihub.QueryProcessor',
                side_effect=self.getQuery).start()
        self.queries = []
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.UpdateProcessor',
                side_effect=self.getUpdate).start()
        self.updates = []

        self.exports = kojihub.RootExports()
        self.exports.getLoggedInUser = mock.MagicMock()
        self.exports.getUser = mock.MagicMock()
        self.exports.hasPerm = mock.MagicMock()
        self.exports.getBuildNotification = mock.MagicMock()
        self.exports.getBuildNotificationBlock = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()


    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub.readPackageList')
    def test_get_notification_recipients_watchers(self, readPackageList, get_user):
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
        readPackageList.assert_not_called()


    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub.readPackageList')
    def test_get_notification_recipients_build_without_tag(self, readPackageList, get_user):
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
        self.assertEqual(q.clauses, [
                                     'package_id = %(package_id)i OR package_id IS NULL',
                                     'tag_id IS NULL',
                                     'user_id IN %(user_ids)s',
                                    ])
        self.assertEqual(q.joins, None)
        self.assertEqual(q.values['user_ids'], [5])

        readPackageList.assert_not_called()

    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub.readPackageList')
    def test_get_notification_recipients_tag_without_build(self, readPackageList, get_user):
        ### with tag without build makes no sense
        build = None
        tag_id = 123
        state = koji.BUILD_STATES['CANCELED']
        self.queries = []

        with self.assertRaises(koji.GenericError):
            kojihub.get_notification_recipients(build, tag_id, state)
        self.assertEqual(self.queries, [])
        readPackageList.assert_not_called()

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

    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub.readPackageList')
    def test_get_notification_recipients_tag_with_build(self, readPackageList, get_user):
        ### with tag and build
        build = {'package_id': 12345, 'owner_name': 'owner_name', 'owner_id': 5}
        tag_id = 123
        state = koji.BUILD_STATES['CANCELED']
        readPackageList.return_value = {12345: {'blocked': False, 'owner_id': 'owner_id'}}
        get_user.return_value = {
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
        self.assertEqual(sorted(emails), ['owner_name@test.domain.com', 'pkg_owner_name@test.domain.com'])


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
        self.assertEqual(q.clauses, [
                                     'package_id = %(package_id)i OR package_id IS NULL',
                                     'tag_id = %(tag_id)i OR tag_id IS NULL',
                                     'user_id IN %(user_ids)s',
                                    ])
        self.assertEqual(q.joins, None)
        self.assertEqual(sorted(q.values['user_ids']), [5, 342])
        readPackageList.assert_called_once_with(pkgID=build['package_id'], tagID=tag_id, inherit=True)
        get_user.asssert_called_once_with(342, strict=True)

    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub.readPackageList')
    def test_get_notification_recipients_blocked_pkg_owner(self, readPackageList, get_user):
        # blocked package owner
        build = {'package_id': 12345, 'owner_name': 'owner_name', 'owner_id': 5}
        tag_id = 123
        state = koji.BUILD_STATES['CANCELED']
        get_user.return_value = {
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

    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub.readPackageList')
    def test_get_notification_recipients_optout(self, readPackageList, get_user):
        # blocked package owner
        build = {'package_id': 12345, 'owner_name': 'owner_name', 'owner_id': 5}
        tag_id = 123
        state = koji.BUILD_STATES['CANCELED']
        get_user.return_value = {
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


    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub.readPackageList')
    def test_get_notification_recipients_machine(self, readPackageList, get_user):
        # package owner is machine
        build = {'package_id': 12345, 'owner_name': 'owner_name', 'owner_id': 5}
        tag_id = 123
        state = koji.BUILD_STATES['CANCELED']
        get_user.return_value = {
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

    #####################
    # Create notification

    @mock.patch('kojihub.get_build_notifications')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_createNotification(self, get_package_id, get_tag_id,
            get_build_notifications):
        user_id = 1
        package_id = 234
        tag_id = 345
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 1}
        self.exports.getUser.return_value = {'id': 2, 'name': 'username'}
        self.exports.hasPerm.return_value = True
        get_package_id.return_value = package_id
        get_tag_id.return_value = tag_id
        get_build_notifications.return_value = []

        r = self.exports.createNotification(user_id, package_id, tag_id, success_only)
        self.assertEqual(r, None)

        self.exports.getLoggedInUser.assert_called_once()
        self.exports.getUser.asssert_called_once_with(user_id)
        self.exports.hasPerm.asssert_called_once_with('admin')
        get_package_id.assert_called_once_with(package_id, strict=True)
        get_tag_id.assert_called_once_with(tag_id, strict=True)
        get_build_notifications.assert_called_once_with(2)
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'build_notifications')
        self.assertEqual(insert.data, {
            'package_id': package_id,
            'user_id': 2,
            'tag_id': tag_id,
            'success_only': success_only,
            'email': 'username@test.domain.com',
        })
        self.assertEqual(insert.rawdata, {})

    @mock.patch('kojihub.get_build_notifications')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_createNotification_unauthentized(self, get_package_id, get_tag_id,
            get_build_notifications):
        user_id = 1
        package_id = 234
        tag_id = 345
        success_only = True
        self.exports.getLoggedInUser.return_value = None

        with self.assertRaises(koji.GenericError):
            self.exports.createNotification(user_id, package_id, tag_id, success_only)

        self.assertEqual(len(self.inserts), 0)

    @mock.patch('kojihub.get_build_notifications')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_createNotification_invalid_user(self, get_package_id, get_tag_id,
            get_build_notifications):
        user_id = 2
        package_id = 234
        tag_id = 345
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 1}
        self.exports.getUser.return_value = None

        with self.assertRaises(koji.GenericError):
            self.exports.createNotification(user_id, package_id, tag_id, success_only)

        self.assertEqual(len(self.inserts), 0)

    @mock.patch('kojihub.get_build_notifications')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_createNotification_no_perm(self, get_package_id, get_tag_id,
            get_build_notifications):
        user_id = 2
        package_id = 234
        tag_id = 345
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 1, 'name': 'a'}
        self.exports.getUser.return_value = {'id': 2, 'name': 'b'}
        self.exports.hasPerm.return_value = False

        with self.assertRaises(koji.GenericError):
            self.exports.createNotification(user_id, package_id, tag_id, success_only)

        self.assertEqual(len(self.inserts), 0)

    @mock.patch('kojihub.get_build_notifications')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_createNotification_invalid_pkg(self, get_package_id, get_tag_id,
            get_build_notifications):
        user_id = 2
        package_id = 234
        tag_id = 345
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 2, 'name': 'a'}
        self.exports.getUser.return_value = {'id': 2, 'name': 'a'}
        get_package_id.side_effect = ValueError

        with self.assertRaises(ValueError):
            self.exports.createNotification(user_id, package_id, tag_id, success_only)

        self.assertEqual(len(self.inserts), 0)

    @mock.patch('kojihub.get_build_notifications')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_createNotification_invalid_tag(self, get_package_id, get_tag_id,
            get_build_notifications):
        user_id = 2
        package_id = 234
        tag_id = 345
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 2, 'name': 'a'}
        self.exports.getUser.return_value = {'id': 2, 'name': 'a'}
        get_package_id.return_value = package_id
        get_tag_id.side_effect = ValueError

        with self.assertRaises(ValueError):
            self.exports.createNotification(user_id, package_id, tag_id, success_only)

        self.assertEqual(len(self.inserts), 0)

    @mock.patch('kojihub.get_build_notifications')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_createNotification_exists(self, get_package_id, get_tag_id,
            get_build_notifications):
        user_id = 2
        package_id = 234
        tag_id = 345
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 2, 'name': 'a'}
        self.exports.getUser.return_value = {'id': 2, 'name': 'a'}
        get_package_id.return_value = package_id
        get_tag_id.return_value = tag_id
        get_build_notifications.return_value = [{
            'package_id': package_id,
            'tag_id': tag_id,
            'success_only': success_only,
        }]

        with self.assertRaises(koji.GenericError):
            self.exports.createNotification(user_id, package_id, tag_id, success_only)

        self.assertEqual(len(self.inserts), 0)

    #####################
    # Delete notification
    @mock.patch('kojihub._dml')
    def test_deleteNotification(self, _dml):
        user_id = 752
        n_id = 543
        self.exports.getBuildNotification.return_value = {'user_id': user_id}

        self.exports.deleteNotification(n_id)

        self.exports.getBuildNotification.assert_called_once_with(n_id, strict=True)
        self.exports.getLoggedInUser.assert_called_once_with()
        _dml.assert_called_once()

    def test_deleteNotification_missing(self):
        n_id = 543
        self.exports.getBuildNotification.side_effect = koji.GenericError

        with self.assertRaises(koji.GenericError):
            self.exports.deleteNotification(n_id)

        self.exports.getBuildNotification.assert_called_once_with(n_id, strict=True)

    def test_deleteNotification_not_logged(self):
        user_id = 752
        n_id = 543
        self.exports.getBuildNotification.return_value = {'user_id': user_id}
        self.exports.getLoggedInUser.return_value = None
        #self.set_queries = ([
        #    [{'user_id': 5, 'email': 'owner_name@%s' % self.context.opts['EmailDomain']}],
        #])

        with self.assertRaises(koji.GenericError):
            self.exports.deleteNotification(n_id)

        self.exports.getBuildNotification.assert_called_once_with(n_id, strict=True)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.queries), 0)

    @mock.patch('kojihub._dml')
    def test_deleteNotification_no_perm(self, _dml):
        user_id = 752
        n_id = 543
        self.exports.getBuildNotification.return_value = {'user_id': user_id}
        self.exports.getLoggedInUser.return_value = {'id': 1}
        self.exports.hasPerm.return_value = False

        with self.assertRaises(koji.GenericError):
            self.exports.deleteNotification(n_id)

        self.exports.getBuildNotification.assert_called_once_with(n_id, strict=True)
        _dml.assert_not_called()


    #####################
    # Update notification
    @mock.patch('kojihub.get_build_notifications')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_updateNotification(self, get_package_id, get_tag_id,
            get_build_notifications):
        n_id = 5432
        user_id = 1
        package_id = 234
        tag_id = 345
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 1}
        self.exports.hasPerm.return_value = True
        get_package_id.return_value = package_id
        get_tag_id.return_value = tag_id
        get_build_notifications.return_value = [{
            'tag_id': tag_id,
            'user_id': user_id,
            'package_id': package_id,
            'success_only': not success_only,
        }]
        self.exports.getBuildNotification.return_value = {'user_id': user_id}

        r = self.exports.updateNotification(n_id, package_id, tag_id, success_only)
        self.assertEqual(r, None)

        self.exports.getLoggedInUser.assert_called_once()
        self.exports.hasPerm.asssert_called_once_with('admin')
        get_package_id.assert_called_once_with(package_id, strict=True)
        get_tag_id.assert_called_once_with(tag_id, strict=True)
        get_build_notifications.assert_called_once_with(user_id)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 1)

    @mock.patch('kojihub.get_build_notifications')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_updateNotification_not_logged(self, get_package_id, get_tag_id,
            get_build_notifications):
        n_id = 5432
        package_id = 234
        tag_id = 345
        success_only = True
        self.exports.getLoggedInUser.return_value = None

        with self.assertRaises(koji.GenericError):
            self.exports.updateNotification(n_id, package_id, tag_id, success_only)

        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    @mock.patch('kojihub.get_build_notifications')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_updateNotification_missing(self, get_package_id, get_tag_id,
            get_build_notifications):
        n_id = 5432
        package_id = 234
        tag_id = 345
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 1}
        self.exports.getBuildNotification.side_effect = koji.GenericError

        with self.assertRaises(koji.GenericError):
            self.exports.updateNotification(n_id, package_id, tag_id, success_only)

        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    @mock.patch('kojihub.get_build_notifications')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_updateNotification_no_perm(self, get_package_id, get_tag_id,
            get_build_notifications):
        n_id = 5432
        user_id = 1
        package_id = 234
        tag_id = 345
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 132}
        self.exports.getBuildNotification.return_value = {'user_id': user_id}
        self.exports.hasPerm.return_value = False

        with self.assertRaises(koji.GenericError):
            self.exports.updateNotification(n_id, package_id, tag_id, success_only)

        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    @mock.patch('kojihub.get_build_notifications')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_updateNotification_exists(self, get_package_id, get_tag_id,
            get_build_notifications):
        n_id = 5432
        user_id = 1
        package_id = 234
        tag_id = 345
        success_only = True
        self.exports.getLoggedInUser.return_value = {'id': 1}
        self.exports.hasPerm.return_value = True
        get_package_id.return_value = package_id
        get_tag_id.return_value = tag_id
        get_build_notifications.return_value = [{
            'tag_id': tag_id,
            'user_id': user_id,
            'package_id': package_id,
            'success_only': success_only,
        }]
        self.exports.getBuildNotification.return_value = {'user_id': user_id}

        with self.assertRaises(koji.GenericError):
            self.exports.updateNotification(n_id, package_id, tag_id, success_only)

        self.exports.getLoggedInUser.assert_called_once()
        self.exports.hasPerm.asssert_called_once_with('admin')
        get_package_id.assert_called_once_with(package_id, strict=True)
        get_tag_id.assert_called_once_with(tag_id, strict=True)
        get_build_notifications.assert_called_once_with(user_id)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    @mock.patch('kojihub.get_build_notifications')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_updateNotification_not_logged(self, get_package_id, get_tag_id,
            get_build_notifications):
        n_id = 5432
        user_id = 1
        package_id = 234
        tag_id = 345
        success_only = True
        self.exports.getLoggedInUser.return_value = None

        with self.assertRaises(koji.GenericError):
            self.exports.updateNotification(n_id, package_id, tag_id, success_only)

        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    ###########################
    # Create notification block

    @mock.patch('kojihub.get_build_notification_blocks')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_createNotificationBlock(self, get_package_id, get_tag_id,
            get_build_notification_blocks):
        user_id = 1
        package_id = 234
        tag_id = 345
        self.exports.getLoggedInUser.return_value = {'id': 1}
        self.exports.getUser.return_value = {'id': 2, 'name': 'username'}
        self.exports.hasPerm.return_value = True
        get_package_id.return_value = package_id
        get_tag_id.return_value = tag_id
        get_build_notification_blocks.return_value = []

        r = self.exports.createNotificationBlock(user_id, package_id, tag_id)
        self.assertEqual(r, None)

        self.exports.getLoggedInUser.assert_called_once()
        self.exports.getUser.asssert_called_once_with(user_id)
        self.exports.hasPerm.asssert_called_once_with('admin')
        get_package_id.assert_called_once_with(package_id, strict=True)
        get_tag_id.assert_called_once_with(tag_id, strict=True)
        get_build_notification_blocks.assert_called_once_with(2)
        self.assertEqual(len(self.inserts), 1)
        insert = self.inserts[0]
        self.assertEqual(insert.table, 'build_notifications_block')
        self.assertEqual(insert.data, {
            'package_id': package_id,
            'user_id': 2,
            'tag_id': tag_id,
        })
        self.assertEqual(insert.rawdata, {})

    @mock.patch('kojihub.get_build_notification_blocks')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_createNotificationBlock_unauthentized(self, get_package_id, get_tag_id,
            get_build_notification_blocks):
        user_id = 1
        package_id = 234
        tag_id = 345
        self.exports.getLoggedInUser.return_value = None

        with self.assertRaises(koji.GenericError):
            self.exports.createNotificationBlock(user_id, package_id, tag_id)

        self.assertEqual(len(self.inserts), 0)

    @mock.patch('kojihub.get_build_notification_blocks')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_createNotificationBlock_invalid_user(self, get_package_id, get_tag_id,
            get_build_notification_blocks):
        user_id = 2
        package_id = 234
        tag_id = 345
        self.exports.getLoggedInUser.return_value = {'id': 1}
        self.exports.getUser.return_value = None

        with self.assertRaises(koji.GenericError):
            self.exports.createNotificationBlock(user_id, package_id, tag_id)

        self.assertEqual(len(self.inserts), 0)

    @mock.patch('kojihub.get_build_notification_blocks')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_createNotificationBlock_no_perm(self, get_package_id, get_tag_id,
            get_build_notification_blocks):
        user_id = 2
        package_id = 234
        tag_id = 345
        self.exports.getLoggedInUser.return_value = {'id': 1, 'name': 'a'}
        self.exports.getUser.return_value = {'id': 2, 'name': 'b'}
        self.exports.hasPerm.return_value = False

        with self.assertRaises(koji.GenericError):
            self.exports.createNotificationBlock(user_id, package_id, tag_id)

        self.assertEqual(len(self.inserts), 0)

    @mock.patch('kojihub.get_build_notification_blocks')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_createNotificationBlock_invalid_pkg(self, get_package_id, get_tag_id,
            get_build_notification_blocks):
        user_id = 2
        package_id = 234
        tag_id = 345
        self.exports.getLoggedInUser.return_value = {'id': 2, 'name': 'a'}
        self.exports.getUser.return_value = {'id': 2, 'name': 'a'}
        get_package_id.side_effect = ValueError

        with self.assertRaises(ValueError):
            self.exports.createNotificationBlock(user_id, package_id, tag_id)

        self.assertEqual(len(self.inserts), 0)

    @mock.patch('kojihub.get_build_notification_blocks')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_createNotificationBlock_invalid_tag(self, get_package_id, get_tag_id,
            get_build_notification_blocks):
        user_id = 2
        package_id = 234
        tag_id = 345
        self.exports.getLoggedInUser.return_value = {'id': 2, 'name': 'a'}
        self.exports.getUser.return_value = {'id': 2, 'name': 'a'}
        get_package_id.return_value = package_id
        get_tag_id.side_effect = ValueError

        with self.assertRaises(ValueError):
            self.exports.createNotificationBlock(user_id, package_id, tag_id)

        self.assertEqual(len(self.inserts), 0)

    @mock.patch('kojihub.get_build_notification_blocks')
    @mock.patch('kojihub.get_tag_id')
    @mock.patch('kojihub.get_package_id')
    def test_createNotificationBlock_exists(self, get_package_id, get_tag_id,
            get_build_notification_blocks):
        user_id = 2
        package_id = 234
        tag_id = 345
        self.exports.getLoggedInUser.return_value = {'id': 2, 'name': 'a'}
        self.exports.getUser.return_value = {'id': 2, 'name': 'a'}
        get_package_id.return_value = package_id
        get_tag_id.return_value = tag_id
        get_build_notification_blocks.return_value = [{
            'package_id': package_id,
            'tag_id': tag_id,
        }]

        with self.assertRaises(koji.GenericError):
            self.exports.createNotificationBlock(user_id, package_id, tag_id)

        self.assertEqual(len(self.inserts), 0)

    ###########################
    # Delete notification block
    @mock.patch('kojihub._dml')
    def test_deleteNotificationBlock(self, _dml):
        user_id = 752
        n_id = 543
        self.exports.getBuildNotificationBlock.return_value = {'user_id': user_id}

        self.exports.deleteNotificationBlock(n_id)

        self.exports.getBuildNotificationBlock.assert_called_once_with(n_id, strict=True)
        self.exports.getLoggedInUser.assert_called_once_with()
        _dml.assert_called_once()

    def test_deleteNotificationBlock_missing(self):
        n_id = 543
        self.exports.getBuildNotificationBlock.side_effect = koji.GenericError

        with self.assertRaises(koji.GenericError):
            self.exports.deleteNotificationBlock(n_id)

        self.exports.getBuildNotificationBlock.assert_called_once_with(n_id, strict=True)

    def test_deleteNotificationBlock_not_logged(self):
        user_id = 752
        n_id = 543
        self.exports.getBuildNotificationBlock.return_value = {'user_id': user_id}
        self.exports.getLoggedInUser.return_value = None
        #self.set_queries = ([
        #    [{'user_id': 5, 'email': 'owner_name@%s' % self.context.opts['EmailDomain']}],
        #])

        with self.assertRaises(koji.GenericError):
            self.exports.deleteNotificationBlock(n_id)

        self.exports.getBuildNotificationBlock.assert_called_once_with(n_id, strict=True)
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.queries), 0)

    @mock.patch('kojihub._dml')
    def test_deleteNotificationBlock_no_perm2(self, _dml):
        user_id = 752
        n_id = 543
        self.exports.getBuildNotificationBlock.return_value = {'user_id': user_id}
        self.exports.getLoggedInUser.return_value = {'id': 1}
        self.exports.hasPerm.return_value = False

        with self.assertRaises(koji.GenericError):
            self.exports.deleteNotificationBlock(n_id)

        self.exports.getBuildNotificationBlock.assert_called_once_with(n_id, strict=True)
        _dml.assert_not_called()
