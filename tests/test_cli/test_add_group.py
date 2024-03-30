from __future__ import absolute_import

import mock
import six
import unittest

from koji_cli.commands import handle_add_group
from . import utils


class TestAddGroup(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s add-group <tag> <group>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_add_group(self, stdout):
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
        self.activate_session_mock.assert_called_once_with(session, options)
        session.hasPerm.assert_called_once_with('admin')
        session.getTag.assert_called_once_with(tag)
        session.getTagGroups.assert_called_once_with(tag, inherit=False)
        session.groupListAdd.assert_called_once_with(tag, group)
        self.assertNotEqual(rv, 1)

    def test_handle_add_group_dupl(self):
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
        self.assert_system_exit(
            handle_add_group,
            options, session, arguments,
            stdout='',
            stderr='Group group already exists for tag tag\n',
            exit_code=1,
            activate_session=None)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(session, options)
        session.hasPerm.assert_called_once_with('admin')
        session.getTag.assert_called_once_with(tag)
        session.getTagGroups.assert_called_once_with(tag, inherit=False)
        session.groupListAdd.assert_not_called()

    def test_handle_add_group_no_args(self):
        arguments = []
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()

        # Run it and check immediate output
        self.assert_system_exit(
            handle_add_group,
            options, session, arguments,
            stdout='',
            stderr=self.format_error_message("Please specify a tag name and a group name"),
            exit_code=2,
            activate_session=None)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_not_called()
        session.hasPerm.assert_not_called()
        session.getTag.assert_not_called()
        session.getTagGroups.assert_not_called()
        session.groupListAdd.assert_not_called()

    def test_handle_add_group_no_perm(self):
        tag = 'tag'
        group = 'group'
        arguments = [tag, group]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.hasPerm.return_value = False

        # Run it and check immediate output
        self.assert_system_exit(
            handle_add_group,
            options, session, arguments,
            stdout='',
            stderr=self.format_error_message('This action requires tag or admin privileges'),
            activate_session=None,
            exit_code=2)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(session, options)
        session.hasPerm.assert_has_calls([mock.call('admin'),
                                          mock.call('tag')])
        session.getTag.assert_not_called()
        session.getTagGroups.assert_not_called()
        session.groupListAdd.assert_not_called()

    def test_handle_add_group_no_tag(self):
        tag = 'tag'
        group = 'group'
        arguments = [tag, group]
        options = mock.MagicMock()

        # Mock out the xmlrpc server
        session = mock.MagicMock()
        session.hasPerm.return_value = True
        session.getTag.return_value = None

        # Run it and check immediate output
        self.assert_system_exit(
            handle_add_group,
            options, session, arguments,
            stdout='',
            stderr='No such tag: tag\n',
            exit_code=1,
            activate_session=None)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(session, options)
        session.hasPerm.assert_called_once_with('admin')
        session.getTag.assert_called_once_with(tag)
        session.getTagGroups.assert_not_called()
        session.groupListAdd.assert_not_called()

    def test_handle_add_group_help(self):
        self.assert_help(
            handle_add_group,
            """Usage: %s add-group <tag> <group>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
