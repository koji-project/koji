from __future__ import absolute_import

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

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_group_nonexistent_tag(self, activate_session_mock, stdout, stderr):
        tag = 'nonexistent-tag'
        group = 'group'
        arguments = [tag, group]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.hasPerm.return_value = True
        session.getTag.return_value = None

        with self.assertRaises(SystemExit):
            handle_remove_group(options, session, arguments)

        # assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.hasPerm.assert_called_once_with('admin')
        session.getTag.assert_called_once_with(tag)
        session.getTagGroups.assert_not_called()
        session.groupListRemove.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_group_nonexistent_group(self, activate_session_mock, stdout, stderr):
        tag = 'tag'
        group = 'group'
        arguments = [tag, group]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.hasPerm.return_value = True
        session.getTag.return_value = tag
        session.getTagGroups.return_value = []

        with self.assertRaises(SystemExit):
            handle_remove_group(options, session, arguments)

        # assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.hasPerm.assert_called_once_with('admin')
        session.getTag.assert_called_once_with(tag)
        session.getTagGroups.assert_called_once_with(tag, inherit=False)
        session.groupListRemove.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_group(self, activate_session_mock, stdout, stderr):
        tag = 'tag'
        group = 'group'
        arguments = [tag, group]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.hasPerm.return_value = True
        session.getTag.return_value = tag
        session.getTagGroups.return_value = [
            {'name': 'group', 'group_id': 'groupId'}]

        rv = handle_remove_group(options, session, arguments)

        # assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.hasPerm.assert_called_once_with('admin')
        session.getTag.assert_called_once_with(tag)
        session.getTagGroups.assert_called_once_with(tag, inherit=False)
        session.groupListRemove.assert_called_once_with(tag, group)
        self.assertEqual(rv, None)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_remove_group_error_handling(self, activate_session_mock, stdout, stderr):
        session = mock.MagicMock()
        options = mock.MagicMock()

        expected = self.format_error_message(
                        "Please specify a tag name and a group name")
        for args in [[], ['tag'], ['tag', 'grp', 'etc']]:
            self.assert_system_exit(
                handle_remove_group,
                options,
                session,
                args,
                stderr=expected,
                activate_session=None)

        # if we don't have 'tag' permission
        session.hasPerm.return_value = False
        with self.assertRaises(SystemExit):
            handle_remove_group(options, session, ['tag', 'grp'])
        activate_session_mock.assert_called_with(session, options)
