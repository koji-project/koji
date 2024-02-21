from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_list_users
from . import utils


class TestListUsers(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s list-users [options]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_users_default_valid(self, stdout):
        arguments = []
        self.session.listUsers.return_value = [{
            'id': 1, 'krb_principals': [],
            'name': 'kojiadmin',
            'status': 0,
            'usertype': 0},
            {'id': 2,
             'krb_principals': [],
             'name': 'testuser',
             'status': 0,
             'usertype': 0},
        ]
        rv = anon_handle_list_users(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = """kojiadmin
testuser
"""
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(rv, None)
        self.session.listUsers.assert_called_once_with(
            userType=koji.USERTYPES['NORMAL'], prefix=None)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_users_with_prefix(self, stdout):
        arguments = ['--prefix', 'koji']
        self.session.listUsers.return_value = [{
            'id': 1, 'krb_principals': [],
            'name': 'kojiadmin',
            'status': 0,
            'usertype': 0},
        ]
        rv = anon_handle_list_users(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = """kojiadmin
"""
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(rv, None)
        self.session.listUsers.assert_called_once_with(
            userType=koji.USERTYPES['NORMAL'], prefix='koji')

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_users_with_usertype(self, stdout):
        arguments = ['--usertype', 'host']
        self.session.listUsers.return_value = [{
            'id': 3, 'krb_principals': [],
            'name': 'kojihost',
            'status': 0,
            'usertype': 1},
            {'id': 5, 'krb_principals': [],
             'name': 'testhost',
             'status': 0,
             'usertype': 1},
        ]
        rv = anon_handle_list_users(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = """kojihost
testhost
"""
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(rv, None)
        self.session.listUsers.assert_called_once_with(
            userType=koji.USERTYPES['HOST'], prefix=None)

    def test_list_users_with_usertype_non_existing(self):
        arguments = ['--usertype', 'test']
        self.assert_system_exit(
            anon_handle_list_users,
            self.options, self.session, arguments,
            stdout='',
            stderr="Usertype test doesn't exist\n",
            activate_session=None,
            exit_code=1)
        self.session.listUsers.assert_not_called()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_list_users_with_usertype_and_prefix(self, stdout):
        arguments = ['--usertype', 'host', '--prefix', 'test']
        self.session.listUsers.return_value = [{
            'id': 5, 'krb_principals': [],
            'name': 'testhost',
            'status': 0,
            'usertype': 1},
        ]
        rv = anon_handle_list_users(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = """testhost
"""
        self.assertMultiLineEqual(actual, expected)
        self.assertEqual(rv, None)
        self.session.listUsers.assert_called_once_with(
            userType=koji.USERTYPES['HOST'], prefix='test')

    def test_anon_handle_list_users_help(self):
        self.assert_help(
            anon_handle_list_users,
            """Usage: %s list-users [options]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help           show this help message and exit
  --usertype=USERTYPE  List users that have a given usertype (e.g. NORMAL,
                       HOST, GROUP)
  --prefix=PREFIX      List users that have a given prefix
""" % self.progname)
