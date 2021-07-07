from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_unlock_tag
from . import utils


class TestUnlockTag(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_unlock_tag_without_option(self, stderr):
        expected = "Usage: %s unlock-tag [options] <tag> [<tag> ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Please specify a tag\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_unlock_tag(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_unlock_tag_non_exist_tag(self, stderr):
        tag = 'test-tag'
        expected = "Usage: %s unlock-tag [options] <tag> [<tag> ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: No such tag: %s\n" % (self.progname, self.progname, tag)
        self.session.getTag.return_value = None
        with self.assertRaises(SystemExit) as ex:
            handle_unlock_tag(self.options, self.session, [tag])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    def test_unlock_tag_glob(self):
        list_tags = [{'arches': '',
                      'id': 1,
                      'locked': True,
                      'maven_include_all': False,
                      'maven_support': False,
                      'name': 'test-tag',
                      'perm': 'build',
                      'perm_id': 3}]

        self.session.listTags.return_value = list_tags
        self.session.editTag2.return_value = None
        rv = handle_unlock_tag(self.options, self.session, ['test-tag', '--glob'])
        self.assertEqual(rv, None)
        self.session.listTags.assert_called_with()
        self.session.editTag2.assert_called_with(1, locked=False, perm=None)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_unlock_tag_test(self, stdout):
        tag_info = {'arches': 'x86_64',
                    'extra': {},
                    'id': 1,
                    'locked': True,
                    'maven_include_all': False,
                    'maven_support': False,
                    'name': 'test-tag',
                    'perm': 'build',
                    'perm_id': 3}

        self.session.getTag.return_value = tag_info
        rv = handle_unlock_tag(self.options, self.session, ['test-tag', '--test'])
        self.assertEqual(rv, None)
        expected = "Tag test-tag: skipping changes: {'locked': False, 'perm': None}\n"
        self.assert_console_message(stdout, expected)
        self.session.getTag.assert_called_with('test-tag')

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_unlock_tag_not_locked(self, stdout):
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
        rv = handle_unlock_tag(self.options, self.session, ['test-tag'])
        self.assertEqual(rv, None)
        expected = "Tag test-tag: not locked\n"
        self.assert_console_message(stdout, expected)
        self.session.getTag.assert_called_with('test-tag')

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_unlock_tag_not_selected(self, stdout):
        list_tags = []

        self.session.listTags.return_value = list_tags
        rv = handle_unlock_tag(self.options, self.session, ['test-tag', '--glob'])
        self.assertEqual(rv, None)
        expected = "No tags matched\n"
        self.assert_console_message(stdout, expected)
        self.session.listTags.assert_called_with()

    def test_lock_tag_help(self):
        self.assert_help(
            handle_unlock_tag,
            """Usage: %s unlock-tag [options] <tag> [<tag> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
  --glob      Treat args as glob patterns
  -n, --test  Test mode
""" % self.progname)
