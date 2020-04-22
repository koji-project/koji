from __future__ import absolute_import

import mock
import six

from koji_cli.commands import handle_block_group
from . import utils


class TestBlockGroup(utils.CliTestCase):
    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s block-group <tag> <group>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_block_group_nonexistent_tag(self, activate_session_mock, stderr):
        tag = 'nonexistent-tag'
        group = 'group'
        arguments = [tag, group]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.hasPerm.return_value = True
        session.getTag.return_value = None

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            handle_block_group(options, session, arguments)
        self.assertExitCode(ex, 1)
        actual = stderr.getvalue()
        expected = 'Unknown tag: %s\n' % tag
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.hasPerm.assert_called_once_with('admin')
        session.getTag.assert_called_once_with(tag)
        session.getTagGroups.assert_not_called()
        session.groupListBlock.assert_not_called()

    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_block_group_nonexistent_group(self, activate_session_mock, stderr):
        tag = 'tag'
        group = 'group'
        arguments = [tag, group]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.hasPerm.return_value = True
        session.getTag.return_value = tag
        session.getTagGroups.return_value = []

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as ex:
            handle_block_group(options, session, arguments)
        self.assertExitCode(ex, 1)
        actual = stderr.getvalue()
        expected = "Group %s doesn't exist within tag %s\n" % (group, tag)
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.hasPerm.assert_called_once_with('admin')
        session.getTag.assert_called_once_with(tag)
        session.getTagGroups.assert_called_once_with(tag, inherit=False)
        session.groupListBlock.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_block_group(self, activate_session_mock, stdout):
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

        # Run it and check immediate output
        rv = handle_block_group(options, session, arguments)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.hasPerm.assert_called_once_with('admin')
        session.getTag.assert_called_once_with(tag)
        session.getTagGroups.assert_called_once_with(tag, inherit=False)
        session.groupListBlock.assert_called_once_with(tag, group)
        self.assertEqual(rv, None)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_block_group_error_handling(self, activate_session_mock, stdout):
        session = mock.MagicMock()
        options = mock.MagicMock()

        expected = self.format_error_message(
                        "Please specify a tag name and a group name")
        for args in [[], ['tag'], ['tag', 'grp', 'etc']]:
            self.assert_system_exit(
                handle_block_group,
                options,
                session,
                args,
                stderr=expected,
                activate_session=None,
                exit_code=2)

        # if we don't have 'admin' permission
        session.hasPerm.return_value = False
        self.assert_system_exit(
            handle_block_group,
            options, session, ['tag', 'grp'],
            stderr=self.format_error_message('This action requires tag or admin privileges'),
            stdout='',
            exit_code=2,
            activate_session=None)
        activate_session_mock.assert_called_with(session, options)
