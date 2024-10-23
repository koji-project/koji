from __future__ import absolute_import

try:
    from unittest import mock
except ImportError:
    import mock
import six

from koji_cli.commands import handle_remove_group
from . import utils


class TestRemoveGroup(utils.CliTestCase):
    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s remove-group <tag> <group>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_group_nonexistent_tag(self, activate_session_mock, stderr, stdout):
        tag = 'nonexistent-tag'
        group = 'group'
        arguments = [tag, group]

        # Mock out the xmlrpc server
        self.session.hasPerm.return_value = True
        self.session.getTag.return_value = None

        expected = 'No such tag: %s\n' % tag
        with self.assertRaises(SystemExit) as ex:
            handle_remove_group(self.options, self.session, arguments)
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)

        # assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.hasPerm.assert_called_once_with('admin')
        self.session.getTag.assert_called_once_with(tag)
        self.session.getTagGroups.assert_not_called()
        self.session.groupListRemove.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_group_nonexistent_group(self, activate_session_mock, stdout, stderr):
        tag = 'tag'
        group = 'group'
        arguments = [tag, group]

        # Mock out the xmlrpc server
        self.session.hasPerm.return_value = True
        self.session.getTag.return_value = tag
        self.session.getTagGroups.return_value = []

        with self.assertRaises(SystemExit):
            handle_remove_group(self.options, self.session, arguments)

        # assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.hasPerm.assert_called_once_with('admin')
        self.session.getTag.assert_called_once_with(tag)
        self.session.getTagGroups.assert_called_once_with(tag, inherit=False)
        self.session.groupListRemove.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_group(self, activate_session_mock, stdout, stderr):
        tag = 'tag'
        group = 'group'
        arguments = [tag, group]

        # Mock out the xmlrpc server
        self.session.hasPerm.return_value = True
        self.session.getTag.return_value = tag
        self.session.getTagGroups.return_value = [
            {'name': 'group', 'group_id': 'groupId'}]

        rv = handle_remove_group(self.options, self.session, arguments)

        # assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.hasPerm.assert_called_once_with('admin')
        self.session.getTag.assert_called_once_with(tag)
        self.session.getTagGroups.assert_called_once_with(tag, inherit=False)
        self.session.groupListRemove.assert_called_once_with(tag, group)
        self.assertEqual(rv, None)

    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_group_error_handling(self, activate_session_mock):
        expected = self.format_error_message("Please specify a tag name and a group name")
        for args in [[], ['tag'], ['tag', 'grp', 'etc']]:
            self.assert_system_exit(
                handle_remove_group,
                self.options,
                self.session,
                args,
                stderr=expected,
                stdout='',
                activate_session=None)

        # if we don't have 'tag' permission
        self.session.hasPerm.return_value = False
        with self.assertRaises(SystemExit):
            handle_remove_group(self.options, self.session, ['tag', 'grp'])
        activate_session_mock.assert_called_with(self.session, self.options)

    def test_handle_remove_group_help(self):
        self.assert_help(
            handle_remove_group,
            """Usage: %s remove-group <tag> <group>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)
