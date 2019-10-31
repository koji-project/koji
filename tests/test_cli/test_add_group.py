from __future__ import absolute_import

import mock
import os
import six
import sys
try:
    import unittest2 as unittest
except ImportError:
    import unittest

from koji_cli.commands import handle_add_group

class TestAddGroup(unittest.TestCase):

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_group(self, activate_session_mock, stdout):
        tag = 'tag'
        group = 'group'
        arguments = [tag, group]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.hasPerm.return_value = True
        session.getTag.return_value = 'dsttag'
        session.getTagGroups.return_value = [
            {'name': 'otherGroup', 'group_id': 'otherGroupId'}]

        # Run it and check immediate output
        rv = handle_add_group(options, session, arguments)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.hasPerm.assert_called_once_with('admin')
        session.getTag.assert_called_once_with(tag)
        session.getTagGroups.assert_called_once_with(tag, inherit=False)
        session.groupListAdd.assert_called_once_with(tag, group)
        self.assertNotEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_group_dupl(self, activate_session_mock, stdout):
        tag = 'tag'
        group = 'group'
        arguments = [tag, group]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.hasPerm.return_value = True
        session.getTag.return_value = 'dsttag'
        session.getTagGroups.return_value = [
            {'name': 'group', 'group_id': 'groupId'}]

        # Run it and check immediate output
        rv = handle_add_group(options, session, arguments)
        actual = stdout.getvalue()
        expected = 'Group group already exists for tag tag\n'
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.hasPerm.assert_called_once_with('admin')
        session.getTag.assert_called_once_with(tag)
        session.getTagGroups.assert_called_once_with(tag, inherit=False)
        session.groupListAdd.assert_not_called()
        self.assertEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_group_help(
            self,
            activate_session_mock,
            stderr,
            stdout):
        arguments = []
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        with self.assertRaises(SystemExit) as cm:
            rv = handle_add_group(options, session, arguments)
        actual_stdout = stdout.getvalue()
        actual_stderr = stderr.getvalue()
        expected_stdout = ''
        progname = os.path.basename(sys.argv[0]) or 'koji'
        expected_stderr = """Usage: %s add-group <tag> <group>
(Specify the --help global option for a list of other help options)

%s: error: Please specify a tag name and a group name
""" % (progname, progname)
        self.assertMultiLineEqual(actual_stdout, expected_stdout)
        self.assertMultiLineEqual(actual_stderr, expected_stderr)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_not_called()
        session.hasPerm.assert_not_called()
        session.getTag.assert_not_called()
        session.getTagGroups.assert_not_called()
        session.groupListAdd.assert_not_called()
        if isinstance(cm.exception, int):
            self.assertEqual(cm.exception, 2)
        else:
            self.assertEqual(cm.exception.code, 2)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_group_no_perm(self, activate_session_mock, stdout):
        tag = 'tag'
        group = 'group'
        arguments = [tag, group]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.hasPerm.return_value = False

        # Run it and check immediate output
        rv = handle_add_group(options, session, arguments)
        actual = stdout.getvalue()
        expected = 'This action requires tag or admin privileges\n'
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.hasPerm.assert_has_calls([mock.call('admin'),
                                          mock.call('tag')])
        session.getTag.assert_not_called()
        session.getTagGroups.assert_not_called()
        session.groupListAdd.assert_not_called()
        self.assertEqual(rv, 1)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.activate_session')
    def test_handle_add_group_no_tag(self, activate_session_mock, stdout):
        tag = 'tag'
        group = 'group'
        arguments = [tag, group]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.hasPerm.return_value = True
        session.getTag.return_value = None

        # Run it and check immediate output
        rv = handle_add_group(options, session, arguments)
        actual = stdout.getvalue()
        expected = 'Unknown tag: tag\n'
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        activate_session_mock.assert_called_once_with(session, options)
        session.hasPerm.assert_called_once_with('admin')
        session.getTag.assert_called_once_with(tag)
        session.getTagGroups.assert_not_called()
        session.groupListAdd.assert_not_called()
        self.assertEqual(rv, 1)


if __name__ == '__main__':
    unittest.main()
