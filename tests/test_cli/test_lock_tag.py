from __future__ import absolute_import

try:
    from unittest import mock
except ImportError:
    import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_lock_tag
from . import utils


class TestLockTag(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.all_perms = [{'id': 1, 'name': 'admin'},
                          {'id': 2, 'name': 'appliance'},
                          {'id': 3, 'name': 'build'},
                          {'id': 4, 'name': 'dist-repo'},
                          {'id': 5, 'name': 'host'},
                          {'id': 6, 'name': 'image'},
                          {'id': 7, 'name': 'image-import'},
                          {'id': 8, 'name': 'livecd'},
                          {'id': 9, 'name': 'maven-import'},
                          {'id': 10, 'name': 'repo'},
                          {'id': 11, 'name': 'sign'},
                          {'id': 12, 'name': 'tag'},
                          {'id': 13, 'name': 'target'},
                          {'id': 14, 'name': 'win-admin'},
                          {'id': 15, 'name': 'win-import'}]

    def test_lock_tag_valid(self):
        tag_info = {'arches': 'x86_64',
                    'extra': {},
                    'id': 1,
                    'locked': False,
                    'maven_include_all': False,
                    'maven_support': False,
                    'name': 'test-tag',
                    'perm': None,
                    'perm_id': None}

        perm_id = 3
        perm_name = 'build'
        self.session.getTag.return_value = tag_info
        self.session.getAllPerms.return_value = self.all_perms
        self.session.editTag2.return_value = None
        rv = handle_lock_tag(self.options, self.session, [tag_info['name'], '--perm', perm_name])
        self.assertEqual(rv, None)
        self.session.getTag.assert_called_with(tag_info['name'], strict=True)
        self.session.getAllPerms.assert_called_with()
        self.session.editTag2.assert_called_with(tag_info['id'], perm_id=perm_id)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_lock_tag_valid_2(self, stdout):
        list_tags = [{'arches': '',
                      'id': 1,
                      'locked': True,
                      'maven_include_all': False,
                      'maven_support': False,
                      'name': 'test-tag',
                      'perm': None,
                      'perm_id': None},
                     {'arches': '',
                      'id': 2,
                      'locked': False,
                      'maven_include_all': False,
                      'maven_support': False,
                      'name': 'test-tag-2',
                      'perm': None,
                      'perm_id': None},
                     ]

        self.session.getAllPerms.return_value = self.all_perms
        self.session.listTags.return_value = list_tags
        rv = handle_lock_tag(self.options, self.session, ['test-tag', '--glob', '--master'])
        self.assertEqual(rv, None)
        expected = 'Tag test-tag: master lock already set\n'
        self.assert_console_message(stdout, expected)
        self.session.getAllPerms.assert_called_with()

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_lock_tag_test_option(self, stdout):
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
        self.session.getAllPerms.return_value = self.all_perms
        rv = handle_lock_tag(self.options, self.session, ['test-tag', '--master', '--test'])
        self.assertEqual(rv, None)
        expected = 'Would have set master lock for: test-tag\n'
        self.assert_console_message(stdout, expected)
        self.session.getAllPerms.assert_called_with()
        self.session.getTag.assert_called_with('test-tag', strict=True)

    def test_lock_tag_master_option_not_locked(self):
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
        self.session.getAllPerms.return_value = self.all_perms
        self.session.editTag2.return_value = None
        rv = handle_lock_tag(self.options, self.session, [tag_info['name'], '--master'])
        self.assertEqual(rv, None)
        self.session.getAllPerms.assert_called_with()
        self.session.getTag.assert_called_with('test-tag', strict=True)
        self.session.editTag2.assert_called_with(tag_info['id'], locked=True)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_lock_tag_perms_already(self, stdout):
        tag_info = {'arches': 'x86_64',
                    'extra': {},
                    'id': 1,
                    'locked': False,
                    'maven_include_all': False,
                    'maven_support': False,
                    'name': 'test-tag',
                    'perm': 'build',
                    'perm_id': 3}

        self.session.getTag.return_value = tag_info
        self.session.getAllPerms.return_value = self.all_perms
        rv = handle_lock_tag(self.options, self.session, [tag_info['name'],
                                                          '--perm', tag_info['perm']])
        self.assertEqual(rv, None)
        expected = 'Tag %s: %s permission already required\n' % (tag_info['name'],
                                                                 tag_info['perm'])
        self.assert_console_message(stdout, expected)
        self.session.getAllPerms.assert_called_with()
        self.session.getTag.assert_called_with('test-tag', strict=True)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_lock_tag_test_without_master(self, stdout):
        tag_info = {'arches': 'x86_64',
                    'extra': {},
                    'id': 1,
                    'locked': False,
                    'maven_include_all': False,
                    'maven_support': False,
                    'name': 'test-tag',
                    'perm': 'build',
                    'perm_id': 3}

        self.session.getTag.return_value = tag_info
        self.session.getAllPerms.return_value = self.all_perms
        rv = handle_lock_tag(self.options, self.session, [tag_info['name'], '--test'])
        self.assertEqual(rv, None)
        expected = 'Would have set permission requirement admin for tag %s\n' % (tag_info['name'])
        self.assert_console_message(stdout, expected)
        self.session.getAllPerms.assert_called_with()
        self.session.getTag.assert_called_with('test-tag', strict=True)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_lock_tag_glob_without_tag(self, stdout):
        self.session.getAllPerms.return_value = self.all_perms
        self.session.listTags.return_value = []
        rv = handle_lock_tag(self.options, self.session, ['test-tag', '--glob'])
        self.assertEqual(rv, None)
        expected = 'No tags matched\n'
        self.assert_console_message(stdout, expected)
        self.session.getAllPerms.assert_called_with()

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_lock_tag_without_option(self, stderr):
        expected = "Usage: %s lock-tag [options] <tag> [<tag> ...]\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Please specify a tag\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_lock_tag(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    def test_lock_tag_help(self):
        self.assert_help(
            handle_lock_tag,
            """Usage: %s lock-tag [options] <tag> [<tag> ...]
(Specify the --help global option for a list of other help options)

Options:
  -h, --help   show this help message and exit
  --perm=PERM  Specify permission requirement
  --glob       Treat args as glob patterns
  --master     Lock the master lock
  -n, --test   Test mode
""" % self.progname)
