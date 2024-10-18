from __future__ import absolute_import
try:
    from unittest import mock
except ImportError:
    import mock
import six
import unittest

from koji_cli.commands import anon_handle_list_api
from . import utils


class TestListApi(utils.CliTestCase):
    def setUp(self):
        self.maxDiff = None
        self.error_format = """Usage: %s list-api [options] [method_name ...]
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.session = mock.MagicMock()
        self.options = mock.MagicMock()
        self.ensure_connection = mock.patch('koji_cli.commands.ensure_connection').start()

    def tearDown(self):
        mock.patch.stopall()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_anon_handle_list_api_all_method(self, stdout):
        """Test anon_handle_list_api function"""
        self.session._listapi.return_value = [
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
        anon_handle_list_api(self.options, self.session, [])
        self.assert_console_message(stdout, expected)
        self.ensure_connection.assert_called_once()

    def test_anon_handle_list_api_fake_method(self):
        """Test anon_handle_list_api function"""
        self.session.system.methodHelp.return_value = None
        self.assert_system_exit(
            anon_handle_list_api,
            self.options,
            self.session,
            ['non-existent-fake-method'],
            stderr=self.format_error_message("Unknown method: non-existent-fake-method"),
            activate_session=None)
        self.ensure_connection.assert_called_once()

    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_anon_handle_list_api_specific_method(self, stdout):
        """Test anon_handle_list_api function"""
        self.session.system.methodHelp.return_value = \
            "editTag2(tagInfo, **kwargs)\n  description: Edit information for an existing tag."
        anon_handle_list_api(self.options, self.session, ['editTag2'])
        expected = "editTag2(tagInfo, **kwargs)\n"
        expected += "  description: Edit information for an existing tag.\n"
        self.assert_console_message(stdout, expected)
        self.ensure_connection.assert_called_once()

    def test_anon_handle_list_api_help(self):
        self.assert_help(
            anon_handle_list_api,
            """Usage: %s list-api [options] [method_name ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)


if __name__ == '__main__':
    unittest.main()
