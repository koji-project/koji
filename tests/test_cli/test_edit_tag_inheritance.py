from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_edit_tag_inheritance
from . import utils


class TestEditTagInheritance(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_edit_tag_inheritance_without_option(self, stderr):
        expected = "Usage: %s edit-tag-inheritance [options] <tag> <parent> <priority>\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: This command takes at least one argument: " \
                   "a tag name or ID\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_edit_tag_inheritance(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_edit_tag_inheritance_non_exist_tag(self, stderr):
        tag = 'test-tag'
        parent_tag = 'parent-test-tag'
        priority = '99'
        expected = "Usage: %s edit-tag-inheritance [options] <tag> <parent> <priority>\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such tag: %s\n" % (self.progname, self.progname, tag)
        self.session.getTag.return_value = None
        with self.assertRaises(SystemExit) as ex:
            handle_edit_tag_inheritance(self.options, self.session,
                                        [tag, parent_tag, priority])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_edit_tag_inheritance_non_exist_parent_tag(self, stderr):
        side_effect_result = [{'arches': 'x86_64',
                               'extra': {},
                               'id': 1,
                               'locked': False,
                               'maven_include_all': False,
                               'maven_support': False,
                               'name': 'test-tag',
                               'perm': None,
                               'perm_id': None},
                              None]
        tag = 'test-tag'
        parent_tag = 'parent-test-tag'
        priority = '99'
        expected = "Usage: %s edit-tag-inheritance [options] <tag> <parent> <priority>\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such tag: %s\n" % (self.progname, self.progname, parent_tag)
        self.session.getTag.side_effect = side_effect_result
        with self.assertRaises(SystemExit) as ex:
            handle_edit_tag_inheritance(self.options, self.session,
                                        [tag, parent_tag, priority])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)
