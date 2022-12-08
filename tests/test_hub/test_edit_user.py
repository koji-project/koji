import unittest

import mock

import koji
import kojihub

UP = kojihub.UpdateProcessor
QP = kojihub.QueryProcessor


class TestEditUser(unittest.TestCase):

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
        self.updates = []
        self.get_user = mock.patch('kojihub.kojihub.get_user').start()
        self.verify_name_user = mock.patch('kojihub.kojihub.verify_name_user').start()
        self.context = mock.patch('kojihub.kojihub.context').start()
        self.UpdateProcessor = mock.patch('kojihub.kojihub.UpdateProcessor',
                                          side_effect=self.getUpdate).start()
        # It seems MagicMock will not automatically handle attributes that
        # start with "assert"
        self.context.session.assertLogin = mock.MagicMock()
        self.QueryProcessor = mock.patch('kojihub.kojihub.QueryProcessor',
                                         side_effect=self.getQuery).start()
        self.queries = []
        self.query_singleValue = mock.MagicMock()

    def tearDown(self):
        mock.patch.stopall()

    def test_edit(self):
        self.get_user.return_value = {'id': 333,
                                      'name': 'user',
                                      'krb_principals': ['krb']}
        self.query_singleValue.return_value = None
        self.verify_name_user.return_value = None

        kojihub._edit_user('user', name='newuser')
        # check the update
        self.assertEqual(len(self.updates), 1)
        update = self.updates[0]
        self.assertEqual(update.table, 'users')
        self.assertEqual(update.data, {'name': 'newuser'})
        self.assertEqual(update.values, {'name': 'newuser', 'userID': 333})
        self.assertEqual(update.clauses, ['id = %(userID)i'])

        kojihub._edit_user('user', krb_principal_mappings=[{'old': 'krb', 'new': 'newkrb'}])
        self.context.session.removeKrbPrincipal. \
            assert_called_once_with(333, krb_principal='krb')
        self.context.session.setKrbPrincipal. \
            assert_called_once_with(333, krb_principal='newkrb')

        self.context.reset_mock()
        with self.assertRaises(koji.GenericError) as cm:
            kojihub._edit_user('user',
                               krb_principal_mappings=[{'old': 'krb',
                                                        'new': 'newkrb'},
                                                       {'old': 'newkrb',
                                                        'new': 'newnewkrb'}
                                                       ])
        self.assertEqual(cm.exception.args[0],
                         'There are some conflicts between added and removed'
                         ' Kerberos principals: newkrb')
        self.context.session.removeKrbPrincipal.assert_not_called()
        self.context.session.setKrbPrincipal.assert_not_called()

        self.context.reset_mock()
        with self.assertRaises(koji.GenericError) as cm:
            kojihub._edit_user('user',
                               krb_principal_mappings=[{'old': 'otherkrb',
                                                        'new': 'newkrb'}])
        self.assertEqual(cm.exception.args[0],
                         'Cannot remove non-existent Kerberos principals:'
                         ' otherkrb')
        self.context.session.removeKrbPrincipal.assert_not_called()
        self.context.session.setKrbPrincipal.assert_not_called()

        self.context.reset_mock()
        with self.assertRaises(koji.GenericError) as cm:
            kojihub._edit_user('user',
                               krb_principal_mappings=[{'old': None,
                                                        'new': 'krb'}])
        self.assertEqual(cm.exception.args[0],
                         'Cannot add existing Kerberos principals: krb')
        self.context.session.removeKrbPrincipal.assert_not_called()
        self.context.session.setKrbPrincipal.assert_not_called()

        self.query_singleValue.reset_mock()
        self.query_singleValue.return_value = 2
        with self.assertRaises(koji.GenericError) as cm:
            kojihub._edit_user('user', name='newuser')
        self.assertEqual(cm.exception.args[0],
                         'Name newuser already taken by user 2')

        # name is longer as expected
        new_username = 'new-user+'
        self.verify_name_user.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub._edit_user('user', name=new_username)

        # not except regex rules
        self.verify_name_user.side_effect = koji.GenericError
        with self.assertRaises(koji.GenericError):
            kojihub._edit_user('user', name=new_username)
