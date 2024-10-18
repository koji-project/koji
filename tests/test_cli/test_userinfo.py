from __future__ import absolute_import

try:
    from unittest import mock
except ImportError:
    import mock
from six.moves import StringIO

import koji
from koji_cli.commands import anon_handle_userinfo
from . import utils


class TestUserinfo(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

        self.user = 'test-user'
        self.user_info = {'id': 1,
                          'krb_principals': ['test-principal'],
                          'name': self.user,
                          'status': 0,
                          'groups': ['group1', 'group2'],
                          'usertype': 0}
        self.user_perms = ['admin', 'tag']
        self.count_list_packages = 2
        self.count_list_builds = 3
        self.count_list_tasks = 5

    def __vm(self, result):
        m = koji.VirtualCall('mcall_method', [], {})
        if isinstance(result, dict) and result.get('faultCode'):
            m._result = result
        else:
            m._result = (result,)
        return m

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_userinfo_without_option(self, stderr):
        expected = "Usage: %s userinfo [options] <username> [<username> ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: You must specify at least one " \
                   "username\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            anon_handle_userinfo(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_userinfo_non_exist_user(self, stderr):
        expected_warn = "No such user: %s\n\n" % self.user
        mcall = self.session.multicall.return_value.__enter__.return_value

        mcall.getUser.return_value = self.__vm(None)

        anon_handle_userinfo(self.options, self.session, [self.user])
        self.assert_console_message(stderr, expected_warn)

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_userinfo(self, ensure_connection, stdout):
        expected = """User name: test-user
User ID: 1
krb principals:
  test-principal
Permissions:
  admin
  tag
Groups:
  group1
  group2
Status: NORMAL
Usertype: NORMAL
Number of packages: 2
Number of tasks: 5
Number of builds: 3

"""
        mcall = self.session.multicall.return_value.__enter__.return_value

        mcall.getUser.return_value = self.__vm(self.user_info)
        mcall.getUserPerms.return_value = self.__vm(self.user_perms)
        mcall.listPackages.return_value = self.__vm(self.count_list_packages)
        mcall.listBuilds.return_value = self.__vm(self.count_list_builds)
        mcall.listTasks.return_value = self.__vm(self.count_list_tasks)

        anon_handle_userinfo(self.options, self.session, [self.user])
        self.assert_console_message(stdout, expected)

    def test_userinfo_help(self):
        self.assert_help(
            anon_handle_userinfo,
            """Usage: %s userinfo [options] <username> [<username> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)
