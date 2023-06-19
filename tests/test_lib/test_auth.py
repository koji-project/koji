from __future__ import absolute_import

import mock

import unittest

import koji
import datetime
import kojihub.auth

UP = kojihub.auth.UpdateProcessor
QP = kojihub.auth.QueryProcessor


class TestAuthSession(unittest.TestCase):
    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = self.query_execute
        query.executeOne = self.query_executeOne
        query.singleValue = self.query_singleValue
        self.queries.append(query)
        return query

    def setUp(self):
        self.context = mock.patch('kojihub.auth.context').start()
        kojihub.db.context = self.context
        kojihub.auth.context = self.context
        self.UpdateProcessor = mock.patch('kojihub.auth.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.query_execute = mock.MagicMock()
        self.query_executeOne = mock.MagicMock()
        self.query_singleValue = mock.MagicMock()
        self.QueryProcessor = mock.patch('kojihub.auth.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertLogin = mock.MagicMock()

    def test_instance(self):
        """Simple kojihub.auth.Session instance"""
        self.context.opts = {
            'CheckClientIP': True,
            'DisableURLSessions': False,
            'SessionRenewalTimeout': 0,
        }
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.auth.Session()
        # no args in request/environment
        self.assertEqual(cm.exception.args[0], "'session-id' not specified in session args")

    def get_session_old(self):
        """auth.Session instance"""
        # base session from test_basic_instance
        # url-based kojihub.auth - will be dropped in 1.34
        self.context.opts = {
            'CheckClientIP': True,
            'DisableURLSessions': False,
            'SessionRenewalTimeout': 0,
        }
        self.context.environ = {
            'QUERY_STRING': 'session-id=123&session-key=xyz&callnum=345',
            'REMOTE_ADDR': 'remote-addr',
        }

        self.query_executeOne.side_effect = [
            {'authtype': 2, 'callnum': 1, "date_part('epoch', start_time)": 1666599426.227002,
             "date_part('epoch', update_time)": 1666599426.254308, 'exclusive': None,
             'expired': False, 'master': None,
             'start_time': datetime.datetime(2022, 10, 24, 8, 17, 6, 227002,
                                             tzinfo=datetime.timezone.utc),
             'update_time': datetime.datetime(2022, 10, 24, 8, 17, 6, 254308,
                                              tzinfo=datetime.timezone.utc),
             'user_id': 1},
            {'name': 'kojiadmin', 'status': 0, 'usertype': 0}]
        self.query_singleValue.return_value = 123
        s = kojihub.auth.Session()
        return s, self.context

    def get_session(self):
        # base session from test_basic_instance
        # header-based auth
        self.context.opts = {
            'CheckClientIP': True,
            'DisableURLSessions': True,
            'SessionRenewalTimeout': 0,
        }
        self.context.environ = {
            'HTTP_KOJI_SESSION_ID': '123',
            'HTTP_KOJI_SESSION_KEY': 'xyz',
            'HTTP_KOJI_CALLNUM': '345',
            'REMOTE_ADDR': 'remote-addr',
        }

        self.query_executeOne.side_effect = [
            {'authtype': 2, 'callnum': 1, "date_part('epoch', start_time)": 1666599426.227002,
             "date_part('epoch', update_time)": 1666599426.254308, 'exclusive': None,
             'expired': False, 'master': None,
             'start_time': datetime.datetime(2022, 10, 24, 8, 17, 6, 227002,
                                             tzinfo=datetime.timezone.utc),
             'update_time': datetime.datetime(2022, 10, 24, 8, 17, 6, 254308,
                                              tzinfo=datetime.timezone.utc),
             'user_id': 1},
            {'name': 'kojiadmin', 'status': 0, 'usertype': 0}]
        self.query_singleValue.return_value = 123
        s = kojihub.auth.Session()
        return s, self.context

    def test_session_old(self):
        self.get_session_old()

    def test_renewal_timeout(self):
        """Simple kojihub.auth.Session instance"""
        self.context.opts = {
            'CheckClientIP': True,
            'DisableURLSessions': False,
            'SessionRenewalTimeout': 1440,
        }
        self.context.environ = {
            'QUERY_STRING': 'session-id=123&session-key=xyz&callnum=345',
            'REMOTE_ADDR': 'remote-addr',
        }

        self.query_executeOne.side_effect = [
            {'authtype': 2, 'callnum': 1, "start_ts": 1666599426.227002,
             "update_ts": 1666599426.254308, 'exclusive': None,
             'expired': False, 'master': None,
             'start_time': datetime.datetime(2022, 10, 24, 8, 17, 6, 227002,
                                             tzinfo=datetime.timezone.utc),
             'update_time': datetime.datetime(2022, 10, 24, 8, 17, 6, 254308,
                                              tzinfo=datetime.timezone.utc),
             'renew_ts': None,
             'user_id': 1},
            {'name': 'kojiadmin', 'status': 0, 'usertype': 0}]
        with self.assertRaises(koji.GenericError) as cm:
            kojihub.auth.Session()
        # no args in request/environment
        self.assertEqual(cm.exception.args[0], 'session "123" has expired')

        self.assertEqual(len(self.updates), 1)
        self.assertEqual(len(self.queries), 1)

        update = self.updates[0]

        self.assertEqual(update.table, 'sessions')
        self.assertEqual(update.values['id'], 123)
        self.assertEqual(update.clauses, ['id = %(id)s OR master = %(id)s'])
        self.assertEqual(update.data, {'expired': True})
        self.assertEqual(update.rawdata, {})

        query = self.queries[0]
        self.assertEqual(query.tables, ['sessions'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['closed IS FALSE', 'hostip = %(hostip)s', 'id = %(id)i',
                                         'key = %(key)s'])
        self.assertEqual(query.columns, ['authtype', 'callnum', 'exclusive', 'expired', 'master',
                                         'renew_time', "date_part('epoch', renew_time)",
                                         'start_time', "date_part('epoch', start_time)",
                                         'update_time', "date_part('epoch', update_time)",
                                         'user_id'])
        self.assertEqual(query.aliases, ['authtype', 'callnum', 'exclusive', 'expired', 'master',
                                         'renew_time', 'renew_ts', 'start_time', 'start_ts',
                                         'update_time', 'update_ts', 'user_id'])
        self.assertEqual(query.values, {'id': 123, 'key': 'xyz', 'hostip': 'remote-addr'})

    def test_basic_instance(self):
        """auth.Session instance"""
        s, cntext = self.get_session()
        self.assertEqual(len(self.updates), 2)
        update = self.updates[0]

        self.assertEqual(update.table, 'sessions')
        self.assertEqual(update.values['id'], 123)
        self.assertEqual(update.clauses, ['id = %(id)i'])
        self.assertEqual(update.data, {})
        self.assertEqual(update.rawdata, {'update_time': 'NOW()'})

        update = self.updates[1]

        self.assertEqual(update.table, 'sessions')
        self.assertEqual(update.values['id'], 123)
        self.assertEqual(update.clauses, ['id = %(id)i'])
        self.assertEqual(update.data, {'callnum': 345})
        self.assertEqual(update.rawdata, {})

        self.assertEqual(len(self.queries), 3)

        query = self.queries[0]
        self.assertEqual(query.tables, ['sessions'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['closed IS FALSE', 'hostip = %(hostip)s', 'id = %(id)i',
                                         'key = %(key)s'])
        self.assertEqual(query.columns, ['authtype', 'callnum', 'exclusive', 'expired', 'master',
                                         'renew_time', "date_part('epoch', renew_time)",
                                         'start_time', "date_part('epoch', start_time)",
                                         'update_time', "date_part('epoch', update_time)",
                                         'user_id'])
        self.assertEqual(query.aliases, ['authtype', 'callnum', 'exclusive', 'expired', 'master',
                                         'renew_time', 'renew_ts', 'start_time', 'start_ts',
                                         'update_time', 'update_ts', 'user_id'])
        self.assertEqual(query.values, {'id': 123, 'key': 'xyz', 'hostip': 'remote-addr'})

        query = self.queries[1]
        self.assertEqual(query.tables, ['users'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['id=%(user_id)s'])
        self.assertEqual(query.columns, ['name', 'status', 'usertype'])
        self.assertEqual(query.values, {'user_id': 1})

        query = self.queries[2]
        self.assertEqual(query.tables, ['sessions'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['closed = FALSE', 'exclusive = TRUE',
                                         'user_id=%(user_id)s'])
        self.assertEqual(query.columns, ['id'])

    def test_getattr(self):
        """auth.Session instance"""
        s, cntext = self.get_session()

        self.assertEqual(len(self.updates), 2)
        update = self.updates[0]

        self.assertEqual(update.table, 'sessions')
        self.assertEqual(update.values['id'], 123)
        self.assertEqual(update.clauses, ['id = %(id)i'])
        self.assertEqual(update.data, {})
        self.assertEqual(update.rawdata, {'update_time': 'NOW()'})

        update = self.updates[1]

        self.assertEqual(update.table, 'sessions')
        self.assertEqual(update.values['id'], 123)
        self.assertEqual(update.clauses, ['id = %(id)i'])
        self.assertEqual(update.data, {'callnum': 345})
        self.assertEqual(update.rawdata, {})

        self.assertEqual(len(self.queries), 3)

        query = self.queries[0]
        self.assertEqual(query.tables, ['sessions'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['closed IS FALSE', 'hostip = %(hostip)s', 'id = %(id)i',
                                         'key = %(key)s'])
        self.assertEqual(query.columns, ['authtype', 'callnum', 'exclusive', 'expired', 'master',
                                         'renew_time', "date_part('epoch', renew_time)",
                                         'start_time', "date_part('epoch', start_time)",
                                         'update_time', "date_part('epoch', update_time)",
                                         'user_id'])
        self.assertEqual(query.aliases, ['authtype', 'callnum', 'exclusive', 'expired', 'master',
                                         'renew_time', 'renew_ts', 'start_time', 'start_ts',
                                         'update_time', 'update_ts', 'user_id'])
        self.assertEqual(query.values, {'id': 123, 'key': 'xyz', 'hostip': 'remote-addr'})

        query = self.queries[1]
        self.assertEqual(query.tables, ['users'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['id=%(user_id)s'])
        self.assertEqual(query.columns, ['name', 'status', 'usertype'])
        self.assertEqual(query.values, {'user_id': 1})

        query = self.queries[2]
        self.assertEqual(query.tables, ['sessions'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['closed = FALSE', 'exclusive = TRUE',
                                         'user_id=%(user_id)s'])
        self.assertEqual(query.columns, ['id'])

        # all other names should raise error
        with self.assertRaises(AttributeError):
            s.non_existing_attribute

    def test_str(self):
        """auth.Session string representation"""
        s, cntext = self.get_session()
        self.context.cnx = cntext.cnx

        s.logged_in = False
        s.message = 'msg'
        self.assertEqual(str(s), 'session: not logged in (msg)')
        s.logged_in = True
        self.assertNotEqual(str(s), 'session: not logged in')

    def test_validate(self):
        """Session.validate"""
        s, cntext = self.get_session()
        self.context.cnx = cntext.cnx

        s.lockerror = True
        with self.assertRaises(koji.AuthLockError):
            s.validate()

        s.lockerror = False
        self.assertTrue(s.validate())

    def test_makeShared(self):
        """Session.makeShared"""
        s, _ = self.get_session()
        s.makeShared()
        self.assertEqual(len(self.updates), 3)
        # check only last update query, first two are tested in test_basic_instance
        update = self.updates[2]

        self.assertEqual(update.table, 'sessions')
        self.assertEqual(update.values['session_id'], 123)
        self.assertEqual(update.clauses, ['id=%(session_id)s'])
        self.assertEqual(update.data, {'exclusive': None})
        self.assertEqual(update.rawdata, {})

        self.assertEqual(len(self.queries), 3)
        # all queries are tested in test_basic_instance

    @mock.patch('socket.gethostbyname')
    def test_get_remote_ip(self, gethostbyname):
        """Session.get_remote_ip"""
        s, _ = self.get_session()

        self.context.opts = {'CheckClientIP': False}
        self.assertEqual(s.get_remote_ip(), '-')

        self.context.opts = {'CheckClientIP': True}
        self.assertEqual(s.get_remote_ip(override='xoverride'), 'xoverride')

        self.context.environ = {'REMOTE_ADDR': '123.123.123.123'}
        self.assertEqual(s.get_remote_ip(), '123.123.123.123')

        gethostbyname.return_value = 'ip'
        self.context.environ = {'REMOTE_ADDR': '127.0.0.1'}
        self.assertEqual(s.get_remote_ip(), 'ip')

    def test_login(self):
        s, _ = self.get_session()

        # already logged in
        with self.assertRaises(koji.GenericError):
            s.login('user', 'password')

        s.logged_in = False
        with self.assertRaises(koji.AuthError):
            s.login('user', 123)
        with self.assertRaises(koji.AuthError):
            s.login('user', '')

        # correct
        s.get_remote_ip = mock.MagicMock()
        s.get_remote_ip.return_value = 'hostip'
        s.checkLoginAllowed = mock.MagicMock()
        s.checkLoginAllowed.return_value = True
        s.createSession = mock.MagicMock()
        s.createSession.return_value = {'session-id': 'session-id'}
        self.query_singleValue.return_value = 123

        result = s.login('user', 'password')

        self.assertEqual(len(self.queries), 4)

        # check only last update query, first three are tested in test_basic_instance
        query = self.queries[3]
        self.assertEqual(query.tables, ['users'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['name = %(user)s', 'password = %(password)s'])
        self.assertEqual(query.columns, ['id'])
        self.assertEqual(query.values, {'user': 'user', 'password': 'password'})

        self.assertEqual(len(self.updates), 2)
        # all updates are tested in test_basic_instance

        self.assertEqual(s.get_remote_ip.call_count, 1)
        self.assertEqual(s.checkLoginAllowed.call_args, mock.call(123))
        self.assertEqual(result, s.createSession.return_value)

        # one more try for non-existing user
        self.query_singleValue.return_value = None
        with self.assertRaises(koji.AuthError):
            s.login('user', 'password')

    def test_checkKrbPrincipal(self):
        s, cntext = self.get_session()
        self.assertIsNone(s.checkKrbPrincipal(None))
        self.context.opts = {'AllowedKrbRealms': '*'}
        self.assertIsNone(s.checkKrbPrincipal('any'))
        self.context.opts = {'AllowedKrbRealms': 'example.com'}
        with self.assertRaises(koji.AuthError) as cm:
            s.checkKrbPrincipal('any')
        self.assertEqual(cm.exception.args[0],
                         'invalid Kerberos principal: any')
        with self.assertRaises(koji.AuthError) as cm:
            s.checkKrbPrincipal('any@')
        self.assertEqual(cm.exception.args[0],
                         'invalid Kerberos principal: any@')
        with self.assertRaises(koji.AuthError) as cm:
            s.checkKrbPrincipal('any@bannedrealm')
        self.assertEqual(cm.exception.args[0],
                         "Kerberos principal's realm:"
                         " bannedrealm is not allowed")
        self.assertIsNone(s.checkKrbPrincipal('user@example.com'))
        self.context.opts = {'AllowedKrbRealms': 'example.com,example.net,example.org'}
        self.assertIsNone(s.checkKrbPrincipal('user@example.net'))

    def test_getUserIdFromKerberos(self):
        krb_principal = 'test-krb-principal'
        self.query_singleValue.return_value = 135
        s, cntext = self.get_session()
        s.checkKrbPrincipal = mock.MagicMock()
        s.checkKrbPrincipal.return_value = True

        s.getUserIdFromKerberos(krb_principal)

        self.assertEqual(len(self.queries), 4)
        # check only last update query, first three are tested in test_basic_instance
        query = self.queries[3]
        self.assertEqual(query.tables, ['users'])
        self.assertEqual(query.joins, ['user_krb_principals ON '
                                       'users.id = user_krb_principals.user_id'])
        self.assertEqual(query.clauses, ['krb_principal = %(krb_principal)s'])
        self.assertEqual(query.columns, ['id'])
        self.assertEqual(query.values, {'krb_principal': krb_principal})

        self.assertEqual(len(self.updates), 2)
        # all updates are tested in test_basic_instance

    def test_getUserId(self):
        self.query_singleValue.return_value = 135
        s, cntext = self.get_session()
        username = 'test-user'

        s.getUserId(username)

        self.assertEqual(len(self.queries), 4)
        # check only last update query, first three are tested in test_basic_instance
        query = self.queries[3]
        self.assertEqual(query.tables, ['users'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['name = %(username)s'])
        self.assertEqual(query.columns, ['id'])
        self.assertEqual(query.values, {'username': username})

        self.assertEqual(len(self.updates), 2)
        # all updates are tested in test_basic_instance

    def test_getHostId(self):
        self.query_singleValue.return_value = 199
        s, cntext = self.get_session()

        s._getHostId()

        self.assertEqual(len(self.queries), 4)
        # check only last update query, first three are tested in test_basic_instance
        query = self.queries[3]
        self.assertEqual(query.tables, ['host'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['user_id = %(uid)d'])
        self.assertEqual(query.columns, ['id'])
        self.assertEqual(query.values, {'uid': 1})

        self.assertEqual(len(self.updates), 2)
        # all updates are tested in test_basic_instance

    def test_logout_not_logged(self):
        s, cntext = self.get_session()
        s.logged_in = False
        with self.assertRaises(koji.AuthError) as cm:
            s.logout()
        self.assertEqual(cm.exception.args[0], 'Not logged in')

    def test_logout_logged(self):
        s, _ = self.get_session()
        s.logged_in = True
        s.logout()

        self.assertEqual(len(self.queries), 3)
        # all queries are tested in test_basic_instance

        self.assertEqual(len(self.updates), 3)
        # check only last update query, first two are tested in test_basic_instance
        update = self.updates[2]

        self.assertEqual(update.table, 'sessions')
        self.assertEqual(update.values, {'id': 123, 'id': 123})
        self.assertEqual(update.clauses, ['id = %(id)i OR master = %(id)i'])
        self.assertEqual(update.data, {'closed': True, 'expired': True, 'exclusive': None})
        self.assertEqual(update.rawdata, {})

    def test_logoutChild_not_logged(self):
        s, cntext = self.get_session()
        s.logged_in = False
        with self.assertRaises(koji.AuthError) as cm:
            s.logoutChild(111)
        self.assertEqual(cm.exception.args[0], 'Not logged in')

    def test_logoutChild_logged(self):
        s, _ = self.get_session()
        s.logged_in = True
        s.logoutChild(111)

        self.assertEqual(len(self.queries), 3)
        # all queries are tested in test_basic_instance

        self.assertEqual(len(self.updates), 3)
        # check only last update query, first two are tested in test_basic_instance
        update = self.updates[2]

        self.assertEqual(update.table, 'sessions')
        self.assertEqual(update.values, {'session_id': 111, 'master': 123})
        self.assertEqual(update.clauses, ['id = %(session_id)i', 'master = %(master)i'])
        self.assertEqual(update.data, {'expired': True, 'exclusive': None, 'closed': True})
        self.assertEqual(update.rawdata, {})

    def test_makeExclusive_not_master(self):
        s, cntext = self.get_session()
        s.master = 333
        with self.assertRaises(koji.GenericError) as cm:
            s.makeExclusive()
        self.assertEqual(cm.exception.args[0], 'subsessions cannot become exclusive')

    def test_makeExclusive_already_exclusive(self):
        s, cntext = self.get_session()
        s.master = None
        s.exclusive = True
        with self.assertRaises(koji.GenericError) as cm:
            s.makeExclusive()
        self.assertEqual(cm.exception.args[0], 'session is already exclusive')

    def test_makeExclusive_without_force(self):
        s, cntext = self.get_session()
        s.master = None
        s.exclusive = False
        self.query_singleValue.return_value = 123

        with self.assertRaises(koji.AuthLockError) as cm:
            s.makeExclusive()
        self.assertEqual(cm.exception.args[0], 'Cannot get exclusive session')

        self.assertEqual(len(self.queries), 5)
        self.assertEqual(len(self.updates), 2)

    def test_makeExclusive(self):
        s, _ = self.get_session()
        s.master = None
        s.exclusive = False
        self.query_singleValue.return_value = 123

        s.makeExclusive(force=True)

        self.assertEqual(len(self.queries), 5)
        # check only last two queries, first two are tested in test_basic_instance

        query = self.queries[3]
        self.assertEqual(query.tables, ['users'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['id=%(user_id)s'])
        self.assertEqual(query.columns, ['id'])
        self.assertEqual(query.values, {'user_id': 1})

        query = self.queries[4]
        self.assertEqual(query.tables, ['sessions'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['closed = FALSE', 'exclusive = TRUE',
                                         'user_id=%(user_id)s'])
        self.assertEqual(query.columns, ['id'])
        self.assertEqual(query.values, {'user_id': 1})

        self.assertEqual(len(self.updates), 4)
        # check only last two update queries, first two are tested in test_basic_instance

        update = self.updates[2]
        self.assertEqual(update.table, 'sessions')
        self.assertEqual(update.values, {'excl_id': 123})
        self.assertEqual(update.clauses, ['id=%(excl_id)s'])
        self.assertEqual(update.data, {'expired': True, 'exclusive': None, 'closed': True})
        self.assertEqual(update.rawdata, {})

        update = self.updates[3]
        self.assertEqual(update.table, 'sessions')
        self.assertEqual(update.values, {'session_id': 123})
        self.assertEqual(update.clauses, ['id=%(session_id)s'])
        self.assertEqual(update.data, {'exclusive': True})
        self.assertEqual(update.rawdata, {})

    def test_checkLoginAllowed(self):
        s, cntext = self.get_session()
        self.query_executeOne.side_effect = [{'name': 'testuser', 'status': 0, 'usertype': 0}]
        s.checkLoginAllowed(2)

        self.assertEqual(len(self.queries), 4)
        query = self.queries[3]
        self.assertEqual(query.tables, ['users'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['id = %(user_id)i'])
        self.assertEqual(query.columns, ['name', 'status', 'usertype'])
        self.assertEqual(query.values, {'user_id': 2})

        self.assertEqual(len(self.updates), 2)

    def test_checkLoginAllowed_not_normal_status(self):
        s, cntext = self.get_session()
        self.query_executeOne.side_effect = [{'name': 'testuser', 'status': 1, 'usertype': 0}]

        with self.assertRaises(koji.AuthError) as cm:
            s.checkLoginAllowed(2)
        self.assertEqual(cm.exception.args[0], 'logins by testuser are not allowed')

        self.assertEqual(len(self.queries), 4)
        query = self.queries[3]
        self.assertEqual(query.tables, ['users'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['id = %(user_id)i'])
        self.assertEqual(query.columns, ['name', 'status', 'usertype'])
        self.assertEqual(query.values, {'user_id': 2})

        self.assertEqual(len(self.updates), 2)

    def test_checkLoginAllowed_not_exist_user(self):
        s, cntext = self.get_session()
        self.query_executeOne.side_effect = [None]

        with self.assertRaises(koji.AuthError) as cm:
            s.checkLoginAllowed(2)
        self.assertEqual(cm.exception.args[0], 'invalid user_id: 2')

        self.assertEqual(len(self.queries), 4)
        query = self.queries[3]
        self.assertEqual(query.tables, ['users'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['id = %(user_id)i'])
        self.assertEqual(query.columns, ['name', 'status', 'usertype'])
        self.assertEqual(query.values, {'user_id': 2})

        self.assertEqual(len(self.updates), 2)

    def test_createUserFromKerberos_invalid_krb(self):
        s, cntext = self.get_session()
        krb_principal = 'test-krb-princ'
        with self.assertRaises(koji.AuthError) as cm:
            s.createUserFromKerberos(krb_principal)
        self.assertEqual(cm.exception.args[0], 'invalid Kerberos principal: %s' % krb_principal)

    def test_createUserFromKerberos_user_not_exists(self):
        self.query_execute.return_value = None
        s, cntext = self.get_session()
        krb_principal = 'test-krb-princ@redhat.com'
        s.createUser = mock.MagicMock()
        s.createUser.return_value = 3
        s.createUserFromKerberos(krb_principal)
        self.assertEqual(len(self.queries), 4)
        self.assertEqual(len(self.updates), 2)

        query = self.queries[3]
        self.assertEqual(query.tables, ['users'])
        self.assertEqual(query.joins, ['LEFT JOIN user_krb_principals ON '
                                       'users.id = user_krb_principals.user_id'])
        self.assertEqual(query.clauses, ['name = %(user_name)s'])
        self.assertEqual(query.columns, ['id', 'krb_principal'])
        self.assertEqual(query.values, {'user_name': 'test-krb-princ'})

    def test_createUserFromKerberos_valid(self):
        self.query_execute.return_value = [{'id': 1, 'krb_principal': 'krb-user-1@redhat.com'},
                                           {'id': 1, 'krb_principal': 'krb-user-2@redhat.com'}]
        s, cntext = self.get_session()
        krb_principal = 'test-krb-princ@redhat.com'
        s.setKrbPrincipal = mock.MagicMock()
        s.setKrbPrincipal.return_value = 1
        s.createUserFromKerberos(krb_principal)
        self.assertEqual(len(self.queries), 4)
        self.assertEqual(len(self.updates), 2)

        query = self.queries[3]
        self.assertEqual(query.tables, ['users'])
        self.assertEqual(query.joins, ['LEFT JOIN user_krb_principals ON '
                                       'users.id = user_krb_principals.user_id'])
        self.assertEqual(query.clauses, ['name = %(user_name)s'])
        self.assertEqual(query.columns, ['id', 'krb_principal'])
        self.assertEqual(query.values, {'user_name': 'test-krb-princ'})

    # functions outside Session object

    def test_get_user_data(self):
        """auth.get_user_data"""
        self.query_executeOne.return_value = None
        self.assertEqual(len(self.queries), 0)

        self.query_executeOne.return_value = {'name': 'name', 'status': 'status',
                                              'usertype': 'usertype'}
        kojihub.auth.get_user_data(1)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['users'])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ['id=%(user_id)s'])
        self.assertEqual(query.columns, ['name', 'status', 'usertype'])

    def test_get_user_groups(self):
        """auth.get_user_groups"""
        kojihub.auth.get_user_groups(1)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['user_groups'])
        self.assertEqual(query.joins, ['users ON group_id = users.id'])
        self.assertEqual(query.clauses, ['active IS TRUE', 'user_id=%(user_id)i',
                                         'users.usertype=%(t_group)i'])
        self.assertEqual(query.columns, ['group_id', 'name'])

    def test_get_user_perms(self):
        """auth.get_user_perms"""
        kojihub.auth.get_user_perms(1)
        self.assertEqual(len(self.queries), 2)
        query = self.queries[0]
        self.assertEqual(query.tables, ['user_perms'])
        self.assertEqual(query.joins, ['permissions ON perm_id = permissions.id'])
        self.assertEqual(query.clauses, ['active IS TRUE', 'user_id=%(user_id)s'])
        self.assertEqual(query.columns, ['name'])
        query = self.queries[1]
        self.assertEqual(query.tables, ['user_groups'])
        self.assertEqual(query.joins, [
            'LEFT JOIN user_perms ON user_perms.user_id = user_groups.group_id',
            'permissions ON perm_id = permissions.id'])
        self.assertEqual(sorted(query.clauses), sorted([
            'user_groups.active IS TRUE',
            'user_perms.active IS TRUE',
            'user_groups.user_id=%(user_id)s']))
        self.assertEqual(query.columns, ['name'])

    def test_get_user_perms_inherited(self):
        self.query_execute.side_effect = [
            [{'id': 1, 'name': 'perm1'}, {'id': 2, 'name': 'perm2'}],
            [{'id': 3, 'name': 'perm3'}]
        ]
        result = kojihub.auth.get_user_perms(1)
        self.assertEqual(set(result), {'perm1', 'perm2', 'perm3'})

    def test_logout_logged_not_owner(self):
        s, _ = self.get_session()

        s.logged_in = True
        # session_id without admin perms and not owner
        self.context.session.hasPerm.return_value = False
        self.context.session.user_id.return_value = 123
        self.query_singleValue.return_value = None
        with self.assertRaises(koji.ActionNotAllowed) as ex:
            s.logout(session_id=1)
        self.assertEqual("only admins or owner may logout other session", str(ex.exception))
