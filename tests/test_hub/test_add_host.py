import unittest

import mock

import koji
import kojihub

UP = kojihub.UpdateProcessor
IP = kojihub.InsertProcessor
QP = kojihub.QueryProcessor


class TestAddHost(unittest.TestCase):
    def getInsert(self, *args, **kwargs):
        insert = IP(*args, **kwargs)
        insert.execute = mock.MagicMock()
        self.inserts.append(insert)
        return insert

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = mock.MagicMock()
        query.executeOne = mock.MagicMock()
        query.singleValue = self.query_singleValue
        self.queries.append(query)
        return query

    def setUp(self):
        self.InsertProcessor = mock.patch('kojihub.kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.context_db = mock.patch('koji.db.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context_db.session.assertLogin = mock.MagicMock()
        self.context.session.assertPerm = mock.MagicMock()
        self.context.opts = {'HostPrincipalFormat': '-%s-'}
        self.exports = kojihub.RootExports()
        self.verify_host_name = mock.patch('kojihub.kojihub.verify_host_name').start()
        self.verify_name_user = mock.patch('kojihub.kojihub.verify_name_user').start()
        self.get_host = mock.patch('kojihub.kojihub.get_host').start()
        self.nextval = mock.patch('kojihub.kojihub.nextval').start()
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.query_singleValue = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_add_host_exists(self):
        self.verify_host_name.return_value = None
        self.get_host.return_value = {'id': 123}
        with self.assertRaises(koji.GenericError):
            self.exports.addHost('hostname', ['i386', 'x86_64'])
        self.get_host.assert_called_once_with('hostname')
        self.nextval.assert_not_called()
        self.assertEqual(len(self.queries), 0)

    def test_add_host_valid(self):
        self.verify_host_name.return_value = None
        self.get_host.return_value = {}
        self.nextval.return_value = 12
        self.context.session.createUser.return_value = 456
        self.get_user.return_value = None
        self.query_singleValue.return_value = 333

        r = self.exports.addHost('hostname', ['i386', 'x86_64'])
        self.assertEqual(r, 12)

        self.context.session.assertPerm.assert_called_once_with('host')
        self.get_host.assert_called_once_with('hostname')
        self.context.session.createUser.assert_called_once_with(
            'hostname', usertype=koji.USERTYPES['HOST'], krb_principal='-hostname-')
        self.nextval.assert_called_once_with('host_id_seq')
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['channels'])
        self.assertEqual(query.joins, None)
        self.assertEqual(set(query.columns), set(['id']))
        self.assertEqual(set(query.clauses), set(["name = 'default'"]))

    def test_add_host_wrong_user(self):
        self.verify_host_name.return_value = None
        self.get_user.return_value = {
            'id': 1,
            'name': 'hostname',
            'usertype': koji.USERTYPES['NORMAL']
        }
        self.get_host.return_value = {}
        with self.assertRaises(koji.GenericError):
            self.exports.addHost('hostname', ['i386', 'x86_64'])
        self.get_user.assert_called_once_with(userInfo={'name': 'hostname'})
        self.get_host.assert_called_once_with('hostname')
        self.nextval.assert_not_called()
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['channels'])
        self.assertEqual(query.joins, None)
        self.assertEqual(set(query.columns), set(['id']))
        self.assertEqual(set(query.clauses), set(["name = 'default'"]))

    def test_add_host_wrong_user_forced(self):
        self.verify_host_name.return_value = None
        user_id = 123
        self.nextval.return_value = user_id
        self.get_user.return_value = {
            'id': user_id,
            'name': 'hostname',
            'usertype': koji.USERTYPES['NORMAL']
        }
        self.get_host.return_value = {}

        self.exports.addHost('hostname', ['i386', 'x86_64'], force=True)

        self.get_user.assert_called_once_with(userInfo={'name': 'hostname'})
        self.get_host.assert_called_once_with('hostname')
        self.nextval.assert_called_once_with('host_id_seq')
        self.assertEqual(len(self.inserts), 3)
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.values, {'userID': user_id})
        self.assertEqual(update.table, 'users')
        self.assertEqual(update.clauses, ['id = %(userID)i'])
        self.assertEqual(update.data, {'usertype': koji.USERTYPES['HOST']})
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['channels'])
        self.assertEqual(query.joins, None)
        self.assertEqual(set(query.columns), set(['id']))
        self.assertEqual(set(query.clauses), set(["name = 'default'"]))

    def test_add_host_superwrong_user_forced(self):
        self.verify_host_name.return_value = None
        self.get_user.return_value = {
            'id': 123,
            'name': 'hostname',
            'usertype': koji.USERTYPES['GROUP']
        }
        self.get_host.return_value = {}
        self.query_singleValue.return_value = 333

        with self.assertRaises(koji.GenericError) as ex:
            self.exports.addHost('hostname', ['i386', 'x86_64'], force=True)
        self.assertEqual("user hostname already exists and it is not a host", str(ex.exception))

        self.get_user.assert_called_once_with(userInfo={'name': 'hostname'})
        self.get_host.assert_called_once_with('hostname')
        self.nextval.assert_not_called()
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['channels'])
        self.assertEqual(query.joins, None)
        self.assertEqual(set(query.columns), set(['id']))
        self.assertEqual(set(query.clauses), set(["name = 'default'"]))

    def test_add_host_wrong_format(self):
        # name is longer as expected
        hostname = 'host-name+'
        self.verify_host_name.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.addHost(hostname, ['i386', 'x86_64'], force=True)

        # not except regex rules
        self.verify_host_name.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.addHost(hostname, ['i386', 'x86_64'], force=True)

    def test_add_host_krbprincipal_wrong_type(self):
        krb_principal = ['test-krb']
        self.verify_host_name.return_value = None
        self.get_host.return_value = {}
        self.QueryProcessor.return_value = 333
        self.verify_name_user.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.addHost('hostname', ['i386', 'x86_64'], krb_principal=krb_principal)

        self.context.session.assertPerm.assert_called_once_with('host')
        self.get_host.assert_called_once_with('hostname')
        self.context.session.createUser.assert_not_called()
        self.verify_host_name.assert_called_once_with('hostname')
        self.nextval.assert_not_called()
        self.assertEqual(len(self.queries), 1)
        query = self.queries[0]
        self.assertEqual(query.tables, ['channels'])
        self.assertEqual(query.joins, None)
        self.assertEqual(set(query.columns), set(['id']))
        self.assertEqual(set(query.clauses), set(["name = 'default'"]))
