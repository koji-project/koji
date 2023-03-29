import koji
import kojihub
import mock
from .utils import DBQueryTestCase


class TestGetSessionInfo(DBQueryTestCase):
    def setUp(self):
        super(TestGetSessionInfo, self).setUp()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.exports = kojihub.RootExports()
        self.context.session.hasPerm = mock.MagicMock()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.userinfo = {'id': 123, 'name': 'testuser'}
        self.exports.getLoggedInUser = mock.MagicMock()

    def test_get_session_info_not_logged(self):
        self.context.session.logged_in = False
        result = self.exports.getSessionInfo()
        self.assertIsNone(result)

    def test_get_session_info_user_not_admin_and_not_logged_user(self):
        self.context.session.logged_in = True
        self.context.session.hasPerm.return_value = False
        self.get_user.return_value = self.userinfo
        self.exports.getLoggedInUser.return_value = {'id': 159, 'name': 'testuser2'}
        with self.assertRaises(koji.ActionNotAllowed) as ex:
            self.exports.getSessionInfo(user_id='testuser')
        self.assertEqual("only admins or owners may see all active sessions", str(ex.exception))
        self.assertEqual(len(self.queries), 0)

    def test_get_session_info_user_logged_user(self):
        self.context.session.logged_in = True
        self.context.session.hasPerm.return_value = False
        self.get_user.return_value = self.userinfo
        self.exports.getLoggedInUser.return_value = {'id': 123, 'name': 'testuser'}
        self.exports.getSessionInfo(user_id='testuser')
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['sessions'])
        self.assertEqual(query.clauses, ['expired is FALSE', 'user_id = %(user_id)i'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.columns, ['authtype', 'callnum', 'exclusive', 'expired', 'master',
                                         "date_part('epoch', start_time)", 'update_time',
                                         'user_id'])
        self.assertEqual(query.aliases, ['authtype', 'callnum', 'exclusive', 'expired', 'master',
                                         'start_time', 'update_time', 'user_id'])

    def test_get_session_info_user_and_details(self):
        self.context.session.logged_in = True
        self.context.session.hasPerm.return_value = True
        self.exports.getSessionInfo(details=True, user_id='testuser')
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['sessions'])
        self.assertEqual(query.clauses, ['expired is FALSE', 'user_id = %(user_id)i'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.columns, ['authtype', 'callnum', 'exclusive', 'expired', 'hostip',
                                         'id', 'master', "date_part('epoch', start_time)",
                                         'update_time', 'user_id'])
        self.assertEqual(query.aliases, ['authtype', 'callnum', 'exclusive', 'expired', 'hostip',
                                         'id', 'master', 'start_time', 'update_time', 'user_id'])

    def test_get_session_info_user(self):
        self.context.session.logged_in = True
        self.context.session.hasPerm.return_value = True
        self.exports.getSessionInfo(user_id='testuser')
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['sessions'])
        self.assertEqual(query.clauses, ['expired is FALSE', 'user_id = %(user_id)i'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.columns, ['authtype', 'callnum', 'exclusive', 'expired', 'master',
                                         "date_part('epoch', start_time)", 'update_time',
                                         'user_id'])
        self.assertEqual(query.aliases, ['authtype', 'callnum', 'exclusive', 'expired', 'master',
                                         'start_time', 'update_time', 'user_id'])

    def test_get_session_info_details(self):
        self.context.session.logged_in = True
        self.context.session.hasPerm.return_value = True
        self.qp_execute_one_return_value = {'hostip': '10.0.0.0', 'id': 123}
        self.exports.getSessionInfo(details=True)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['sessions'])
        self.assertEqual(query.clauses, ['expired is FALSE', 'id = %(id)i'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.columns, ['authtype', 'callnum', 'exclusive', 'expired', 'hostip',
                                         'id', 'master', "date_part('epoch', start_time)",
                                         'update_time', 'user_id'])
        self.assertEqual(query.aliases, ['authtype', 'callnum', 'exclusive', 'expired', 'hostip',
                                         'id', 'master', 'start_time', 'update_time', 'user_id'])
