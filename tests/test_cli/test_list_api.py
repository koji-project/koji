from __future__ import absolute_import
import mock
import six
import unittest

from koji_cli.commands import anon_handle_list_api
from . import utils


class TestListApi(utils.CliTestCase):

    # Show long diffs in error output...
    maxDiff = None

    def setUp(self):
        self.error_format = """Usage: %s list-api [options] [method_name]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    @mock.patch('koji_cli.commands.ensure_connection')
    def test_anon_handle_list_api(
            self,
            ensure_connection_mock,
            stdout):
        """Test anon_handle_list_api function"""
        session = mock.MagicMock()
        options = mock.MagicMock()

        # Case 1. list all methods
        session._listapi.return_value = [
            {
                'argdesc': '(tagInfo, **kwargs)',
                'doc': 'Edit information for an existing tag.',
                'argspec': [['tagInfo'], None, 'kwargs', None],
                'args': ['tagInfo'],
                'name': 'editTag2'
            },
            {
                'doc': 'Add user to group',
                'argspec': [['group', 'user', 'strict'], None, None, [True]],
                'args': ['group', 'user', ['strict', True]],
                'name': 'addGroupMember'
            },
            {
                'doc': None,
                'argspec': [[], None, None, None],
                'args': [],
                'name': 'host.getID'
            }
        ]
        expected = "addGroupMember(group, user, strict=True)\n"
        expected += "  description: Add user to group\n"
        expected += "editTag2(tagInfo, **kwargs)\n"
        expected += "  description: Edit information for an existing tag.\n"
        expected += "host.getID()\n"
        anon_handle_list_api(options, session, [])
        self.assert_console_message(stdout, expected)

        # Case 2. non-existent fake method
        session.system.methodHelp.return_value = None
        expected = self.format_error_message("Unknown method: non-existent-fake-method")
        self.assert_system_exit(
            anon_handle_list_api,
            options,
            session,
            ['non-existent-fake-method'],
            stderr=expected,
            activate_session=None)

        # Case 3. known method
        session.system.methodHelp.return_value = "editTag2(tagInfo, **kwargs)\n" \
                                          "  description: Edit information for an existing tag."
        anon_handle_list_api(options, session, ['editTag2'])
        expected = "editTag2(tagInfo, **kwargs)\n"
        expected += "  description: Edit information for an existing tag.\n"
        self.assert_console_message(stdout, expected)

    def test_anon_handle_list_api_help(self):
        self.assert_help(
            anon_handle_list_api,
            """Usage: %s list-api [options] [method_name]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
