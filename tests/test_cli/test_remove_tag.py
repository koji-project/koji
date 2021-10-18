from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_remove_tag
from . import utils


class TestRemoveTag(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_remove_tag_without_option(self, stderr):
        expected = "Usage: %s remove-tag [options] <name>\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Please specify a tag to remove\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_remove_tag(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_remove_tag_non_exist_tag(self, stderr):
        tag = 'test-tag'
        expected = "No such tag: %s\n" % tag
        self.session.getTag.return_value = None
        with self.assertRaises(SystemExit) as ex:
            handle_remove_tag(self.options, self.session, [tag])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)

    def test_remove_tag_valid(self):
        tag_info = {'arches': 'x86_64',
                    'extra': {},
                    'id': 1,
                    'locked': False,
                    'maven_include_all': False,
                    'maven_support': False,
                    'name': 'test-tag',
                    'perm': None,
                    'perm_id': None}

        self.session.getTag.return_value = tag_info
        rv = handle_remove_tag(self.options, self.session, [tag_info['name']])
        self.assertEqual(rv, None)
        self.session.deleteTag.assert_called_once_with(tag_info['id'])
        self.session.getTag.assert_called_with(tag_info['name'])

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_remove_tag_without_perms(self, stderr):
        side_effect_result = [False, False]

        tag = 'test-tag'
        self.session.hasPerm.side_effect = side_effect_result
        with self.assertRaises(SystemExit) as ex:
            handle_remove_tag(self.options, self.session, [tag])
        self.assertExitCode(ex, 2)
        expected_msg = """Usage: %s remove-tag [options] <name>
(Specify the --help global option for a list of other help options)

%s: error: This action requires tag or admin privileges
""" % (self.progname, self.progname)
        self.assert_console_message(stderr, expected_msg)
        self.session.deleteTag.assert_not_called()
        self.session.getTag.assert_not_called()

    def test_remove_tag_help(self):
        self.assert_help(
            handle_remove_tag,
            """Usage: %s remove-tag [options] <name>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)
