import mock
import unittest

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
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertLogin = mock.MagicMock()
        self.context.session.assertPerm = mock.MagicMock()
        self.context.opts = {'HostPrincipalFormat': '-%s-'}
        self.exports = kojihub.RootExports()

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('kojihub._dml')
    @mock.patch('kojihub.get_host')
    @mock.patch('kojihub._singleValue')
    def test_add_host_exists(self, _singleValue, get_host, _dml):
        get_host.return_value = {'id': 123}
        with self.assertRaises(koji.GenericError):
            self.exports.addHost('hostname', ['i386', 'x86_64'])
        _dml.assert_not_called()
        get_host.assert_called_once_with('hostname')
        _singleValue.assert_not_called()

    @mock.patch('kojihub._dml')
    @mock.patch('kojihub.get_host')
    @mock.patch('kojihub._singleValue')
    def test_add_host_valid(self, _singleValue, get_host, _dml):
        get_host.return_value = {}
        _singleValue.side_effect = [333, 12]
        self.context.session.createUser.return_value = 456

        r = self.exports.addHost('hostname', ['i386', 'x86_64'])
        self.assertEqual(r, 12)

        self.context.session.assertPerm.assert_called_once_with('host')
        kojihub.get_host.assert_called_once_with('hostname')
        self.context.session.createUser.assert_called_once_with('hostname',
                usertype=koji.USERTYPES['HOST'], krb_principal='-hostname-')
        self.assertEqual(_singleValue.call_count, 2)
        _singleValue.assert_has_calls([
            mock.call("SELECT id FROM channels WHERE name = 'default'"),
            mock.call("SELECT nextval('host_id_seq')", strict=True)
        ])
        self.assertEqual(_dml.call_count, 1)
        _dml.assert_called_once_with("INSERT INTO host (id, user_id, name) VALUES (%(hostID)i, %(userID)i, %(hostname)s)",
                      {'hostID': 12, 'userID': 456, 'hostname': 'hostname'})

    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub._dml')
    @mock.patch('kojihub.get_host')
    @mock.patch('kojihub._singleValue')
    def test_add_host_wrong_user(self, _singleValue, get_host, _dml, get_user):
        get_user.return_value = {
            'id': 1,
            'name': 'hostname',
            'usertype': koji.USERTYPES['NORMAL']
        }
        get_host.return_value = {}
        with self.assertRaises(koji.GenericError):
            self.exports.addHost('hostname', ['i386', 'x86_64'])
        _dml.assert_not_called()
        get_user.assert_called_once_with(userInfo={'name': 'hostname'})
        get_host.assert_called_once_with('hostname')
        _singleValue.assert_called_once()
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)

    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub._dml')
    @mock.patch('kojihub.get_host')
    @mock.patch('kojihub._singleValue')
    def test_add_host_wrong_user_forced(self, _singleValue, get_host, _dml, get_user):
        get_user.return_value = {
            'id': 123,
            'name': 'hostname',
            'usertype': koji.USERTYPES['NORMAL']
        }
        get_host.return_value = {}

        self.exports.addHost('hostname', ['i386', 'x86_64'], force=True)

        _dml.assert_called_once()
        get_user.assert_called_once_with(userInfo={'name': 'hostname'})
        get_host.assert_called_once_with('hostname')
        _singleValue.assert_called()
        self.assertEqual(len(self.inserts), 2)
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.values, {'userID': 123})
        self.assertEqual(update.table, 'users')
        self.assertEqual(update.clauses, ['id = %(userID)i'])
        self.assertEqual(update.data, {'usertype': koji.USERTYPES['HOST']})

    @mock.patch('kojihub.get_user')
    @mock.patch('kojihub._dml')
    @mock.patch('kojihub.get_host')
    @mock.patch('kojihub._singleValue')
    def test_add_host_superwrong_user_forced(self, _singleValue, get_host, _dml, get_user):
        get_user.return_value = {
            'id': 123,
            'name': 'hostname',
            'usertype': koji.USERTYPES['GROUP']
        }
        get_host.return_value = {}

        with self.assertRaises(koji.GenericError):
            self.exports.addHost('hostname', ['i386', 'x86_64'], force=True)

        _dml.assert_not_called()
        get_user.assert_called_once_with(userInfo={'name': 'hostname'})
        get_host.assert_called_once_with('hostname')
        _singleValue.assert_called()
        self.assertEqual(len(self.inserts), 0)
        self.assertEqual(len(self.updates), 0)
