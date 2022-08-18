import unittest

import mock

import koji
import kojihub

UP = kojihub.UpdateProcessor
IP = kojihub.InsertProcessor


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

    def setUp(self):
        self.InsertProcessor = mock.patch('kojihub.InsertProcessor',
                                          side_effect=self.getInsert).start()
        self.inserts = []
        self.UpdateProcessor = mock.patch('kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        self.updates = []
        self.context = mock.patch('kojihub.context').start()
        self.context_db = mock.patch('koji.db.context').start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context_db.session.assertLogin = mock.MagicMock()
        self.context.session.assertPerm = mock.MagicMock()
        self.context.opts = {'HostPrincipalFormat': '-%s-'}
        self.exports = kojihub.RootExports()
        self.verify_host_name = mock.patch('kojihub.verify_host_name').start()
        self.verify_name_user = mock.patch('kojihub.verify_name_user').start()
        self._dml = mock.patch('kojihub._dml').start()
        self.get_host = mock.patch('kojihub.get_host').start()
        self._singleValue = mock.patch('kojihub._singleValue').start()
        self.nextval = mock.patch('kojihub.nextval').start()
        self.get_user = mock.patch('kojihub.get_user').start()

    def tearDown(self):
        mock.patch.stopall()

    def test_add_host_exists(self):
        self.verify_host_name.return_value = None
        self.get_host.return_value = {'id': 123}
        with self.assertRaises(koji.GenericError):
            self.exports.addHost('hostname', ['i386', 'x86_64'])
        self._dml.assert_not_called()
        self.get_host.assert_called_once_with('hostname')
        self._singleValue.assert_not_called()

    def test_add_host_valid(self):
        self.verify_host_name.return_value = None
        self.get_host.return_value = {}
        self._singleValue.return_value = 333
        self.nextval.return_value = 12
        self.context.session.createUser.return_value = 456
        self.get_user.return_value = None

        r = self.exports.addHost('hostname', ['i386', 'x86_64'])
        self.assertEqual(r, 12)

        self.context.session.assertPerm.assert_called_once_with('host')
        kojihub.get_host.assert_called_once_with('hostname')
        self.context.session.createUser.assert_called_once_with(
            'hostname', usertype=koji.USERTYPES['HOST'], krb_principal='-hostname-')
        self._singleValue.assert_called_once_with("SELECT id FROM channels WHERE name = 'default'")
        self.nextval.assert_called_once_with('host_id_seq')
        self.assertEqual(self._dml.call_count, 1)
        self._dml.assert_called_once_with("INSERT INTO host (id, user_id, name) "
                                          "VALUES (%(hostID)i, %(userID)i, %(hostname)s)",
                                          {'hostID': 12, 'userID': 456, 'hostname': 'hostname'})

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
        self._dml.assert_not_called()
        self.get_user.assert_called_once_with(userInfo={'name': 'hostname'})
        self.get_host.assert_called_once_with('hostname')
        self._singleValue.assert_called_once()
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    def test_add_host_wrong_user_forced(self):
        self.verify_host_name.return_value = None
        self.get_user.return_value = {
            'id': 123,
            'name': 'hostname',
            'usertype': koji.USERTYPES['NORMAL']
        }
        self.get_host.return_value = {}

        self.exports.addHost('hostname', ['i386', 'x86_64'], force=True)

        self._dml.assert_called_once()
        self.get_user.assert_called_once_with(userInfo={'name': 'hostname'})
        self.get_host.assert_called_once_with('hostname')
        self._singleValue.assert_called()
        self.assertEqual(len(self.inserts), 2)
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.values, {'userID': 123})
        self.assertEqual(update.table, 'users')
        self.assertEqual(update.clauses, ['id = %(userID)i'])
        self.assertEqual(update.data, {'usertype': koji.USERTYPES['HOST']})

    def test_add_host_superwrong_user_forced(self):
        self.verify_host_name.return_value = None
        self.get_user.return_value = {
            'id': 123,
            'name': 'hostname',
            'usertype': koji.USERTYPES['GROUP']
        }
        self.get_host.return_value = {}

        with self.assertRaises(koji.GenericError):
            self.exports.addHost('hostname', ['i386', 'x86_64'], force=True)

        self._dml.assert_not_called()
        self.get_user.assert_called_once_with(userInfo={'name': 'hostname'})
        self.get_host.assert_called_once_with('hostname')
        self._singleValue.assert_called()
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

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
        self._singleValue.side_effect = [333, 12]
        self.verify_name_user.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            self.exports.addHost('hostname', ['i386', 'x86_64'], krb_principal=krb_principal)

        self.context.session.assertPerm.assert_called_once_with('host')
        kojihub.get_host.assert_called_once_with('hostname')
        self.context.session.createUser.assert_not_called()
        self.assertEqual(self._singleValue.call_count, 1)
        self._singleValue.assert_called_once_with("SELECT id FROM channels WHERE name = 'default'")
        self.verify_host_name.assert_called_once_with('hostname')
