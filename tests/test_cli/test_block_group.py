from __future__ import absolute_import

import mock
import six
import koji

from koji_cli.commands import handle_block_group
from . import utils


class TestBlockGroup(utils.CliTestCase):
    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.maxDiff = None
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s block-group <tag> <group>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    def test_handle_block_group_nonexistent_tag(self):
        tag = 'nonexistent-tag'
        group = 'group'
        arguments = [tag, group]
        self.session.hasPerm.return_value = True
        self.session.getTag.return_value = None

        # Run it and check immediate output
        self.assert_system_exit(
            handle_block_group,
            self.options, self.session, arguments,
            stderr='No such tag: %s\n' % tag,
            stdout='',
            activate_session=None,
            exit_code=1)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.hasPerm.assert_called_once_with('admin')
        self.session.getTag.assert_called_once_with(tag)
        self.session.getTagGroups.assert_not_called()
        self.session.groupListBlock.assert_not_called()

    def test_handle_block_group_nonexistent_group(self):
        tag = 'tag'
        group = 'group'
        arguments = [tag, group]
        self.session.hasPerm.return_value = True
        self.session.getTag.return_value = tag
        self.session.getTagGroups.return_value = []

        # Run it and check immediate output
        self.assert_system_exit(
            handle_block_group,
            self.options, self.session, arguments,
            stderr="Group %s doesn't exist within tag %s\n" % (group, tag),
            stdout='',
            activate_session=None,
            exit_code=1)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.hasPerm.assert_called_once_with('admin')
        self.session.getTag.assert_called_once_with(tag)
        self.session.getTagGroups.assert_called_once_with(tag, inherit=False)
        self.session.groupListBlock.assert_not_called()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_handle_block_group(self, stdout):
        tag = 'tag'
        group = 'group'
        arguments = [tag, group]
        self.session.hasPerm.return_value = True
        self.session.getTag.return_value = tag
        self.session.getTagGroups.return_value = [
            {'name': 'group', 'group_id': 'groupId'}]

        # Run it and check immediate output
        rv = handle_block_group(self.options, self.session, arguments)
        actual = stdout.getvalue()
        expected = ''
        self.assertMultiLineEqual(actual, expected)

        # Finally, assert that things were called as we expected.
        self.activate_session_mock.assert_called_once_with(self.session, self.options)
        self.session.hasPerm.assert_called_once_with('admin')
        self.session.getTag.assert_called_once_with(tag)
        self.session.getTagGroups.assert_called_once_with(tag, inherit=False)
        self.session.groupListBlock.assert_called_once_with(tag, group)
        self.assertEqual(rv, None)

    def test_handle_block_group_error_handling(self):
        expected = self.format_error_message(
            "Please specify a tag name and a group name")
        for args in [[], ['tag'], ['tag', 'grp', 'etc']]:
            self.assert_system_exit(
                handle_block_group,
                self.options, self.session, args,
                stderr=expected,
                stdout='',
                activate_session=None,
                exit_code=2)

        # if we don't have 'admin' permission
        self.session.hasPerm.return_value = False
        self.assert_system_exit(
            handle_block_group,
            self.options, self.session, ['tag', 'grp'],
            stderr=self.format_error_message('This action requires tag or admin privileges'),
            stdout='',
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_called_with(self.session, self.options)

    def test_handle_block_group_help(self):
        self.assert_help(
            handle_block_group,
            """Usage: %s block-group <tag> <group>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)
