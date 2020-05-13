from __future__ import absolute_import

import mock

try:
    import unittest2 as unittest
except ImportError:
    import unittest
import six

import koji
import koji.auth


class TestAuthSession(unittest.TestCase):
    def test_instance(self):
        """Simple auth.Session instance"""
        s = koji.auth.Session()
        # no args in request/environment
        self.assertEqual(s.message, 'no session args')

    @mock.patch('koji.auth.context')
    def get_session(self, context):
        """auth.Session instance"""
        # base session from test_basic_instance
        context.environ = {
            'QUERY_STRING': 'session-id=123&session-key=xyz&callnum=345',
            'REMOTE_ADDR': 'remote-addr',
        }
        cursor = mock.MagicMock(name='cursor')
        context.cnx.cursor.return_value = cursor
        cursor.fetchone.side_effect = [
            # get session
            [koji.AUTHTYPE_NORMAL, 344, False, False, 'master', 'start_time',
             'start_ts', 'update_time', 'update_ts', 'user_id'],
            # get user
            ['name', koji.USER_STATUS['NORMAL'], koji.USERTYPES['NORMAL']],
            # get excl.session
            None,
            # upd. timestamp
            None,
            # upd callnum
            None,
        ]

        s = koji.auth.Session()
        return s, context, cursor

    @mock.patch('koji.auth.context')
    def test_basic_instance(self, context):
        """auth.Session instance"""
        s, cntext, cursor = self.get_session()
        context.cnx = cntext.cnx

        self.assertEqual(s.id, 123)
        self.assertEqual(s.key, 'xyz')
        self.assertEqual(s.hostip, 'remote-addr')
        self.assertEqual(s.callnum, 345)
        self.assertEqual(s.user_id, 'user_id')
        self.assertEqual(s.authtype, koji.AUTHTYPE_NORMAL)
        self.assertEqual(s.master, 'master')
        self.assertTrue(s.logged_in)

        # 5 SQL calls: get session, get user, get excl. session,
        # update timestamp, update callnum
        self.assertEqual(cursor.execute.call_count, 5)

    @mock.patch('koji.auth.context')
    def test_getattr(self, context):
        """auth.Session instance"""
        s, cntext, cursor = self.get_session()
        context.cnx = cntext.cnx

        # test
        self.assertEqual(s.perms, {})
        self.assertEqual(s.groups, {})
        self.assertEqual(s.host_id, None)
        # all other names should raise error
        with self.assertRaises(AttributeError):
            s.non_existing_attribute

    @mock.patch('koji.auth.context')
    def test_str(self, context):
        """auth.Session string representation"""
        s, cntext, cursor = self.get_session()
        context.cnx = cntext.cnx

        s.logged_in = False
        s.message = 'msg'
        self.assertEqual(str(s), 'session: not logged in (msg)')
        s.logged_in = True
        self.assertNotEqual(str(s), 'session: not logged in')

    @mock.patch('koji.auth.context')
    def test_validate(self, context):
        """Session.validate"""
        s, cntext, cursor = self.get_session()
        context.cnx = cntext.cnx

        s.lockerror = True
        with self.assertRaises(koji.AuthLockError):
            s.validate()

        s.lockerror = False
        self.assertTrue(s.validate())

    @mock.patch('koji.auth.context')
    def test_makeShared(self, context):
        """Session.makeShared"""
        s, cntext, cursor = self.get_session()
        context.cnx = cntext.cnx

        s.makeShared()
        c = cursor.execute.call_args[0]
        self.assertEqual(c[0],
                         'UPDATE sessions SET "exclusive"=NULL WHERE id=%(session_id)s')
        self.assertEqual(c[1]['session_id'], 123)

    @mock.patch('socket.gethostbyname')
    @mock.patch('koji.auth.context')
    def test_get_remote_ip(self, context, gethostbyname):
        """Session.get_remote_ip"""
        s, cntext, cursor = self.get_session()

        context.opts = {'CheckClientIP': False}
        self.assertEqual(s.get_remote_ip(), '-')

        context.opts = {'CheckClientIP': True}
        self.assertEqual(s.get_remote_ip(override='xoverride'), 'xoverride')

        context.environ = {'REMOTE_ADDR': '123.123.123.123'}
        self.assertEqual(s.get_remote_ip(), '123.123.123.123')

        gethostbyname.return_value = 'ip'
        context.environ = {'REMOTE_ADDR': '127.0.0.1'}
        self.assertEqual(s.get_remote_ip(), 'ip')

    @mock.patch('koji.auth.context')
    def test_login(self, context):
        s, cntext, cursor = self.get_session()
        context.cnx = cntext.cnx

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
        cursor.fetchone = mock.MagicMock()
        cursor.fetchone.return_value = ['user_id']
        result = s.login('user', 'password')

        self.assertEqual(s.get_remote_ip.call_count, 1)
        self.assertEqual(s.checkLoginAllowed.call_args, mock.call('user_id'))
        self.assertEqual(result, s.createSession.return_value)

        # one more try for non-existing user
        cursor.fetchone.return_value = None
        with self.assertRaises(koji.AuthError):
            s.login('user', 'password')

    @mock.patch('koji.auth.context')
    def test_checkKrbPrincipal(self, context):
        s, cntext, cursor = self.get_session()
        self.assertIsNone(s.checkKrbPrincipal(None))
        context.opts = {'AllowedKrbRealms': '*'}
        self.assertIsNone(s.checkKrbPrincipal('any'))
        context.opts = {'AllowedKrbRealms': 'example.com'}
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
        context.opts = {'AllowedKrbRealms': 'example.com,example.net'
                                            ' , example.org'}
        self.assertIsNone(s.checkKrbPrincipal('user@example.net'))

    # functions outside Session object

    @mock.patch('koji.auth.context')
    def test_get_user_data(self, context):
        """koji.auth.get_user_data"""
        cursor = mock.MagicMock(name='cursor')
        context.cnx.cursor.return_value = cursor
        cursor.fetchone.return_value = ['name', 'status', 'usertype']

        self.assertEqual(sorted(koji.auth.get_user_data(1).items()),
                         sorted({'name': 'name', 'status': 'status',
                                 'usertype': 'usertype'}.items()))

        cursor.fetchone.return_value = None
        self.assertEqual(koji.auth.get_user_data(1), None)
