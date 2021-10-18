from __future__ import absolute_import

import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_add_target
from . import utils


class TestAddTarget(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_add_target_without_option(self, stderr):
        expected = "Usage: %s add-target <name> <build tag> <dest tag>\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Please specify a target name, a build tag, " \
                   "and destination tag\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_add_target(self.options, self.session, [])
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_add_target_non_exist_tag(self, stderr):
        target = 'test-target'
        tag = 'test-tag'
        dest_tag = 'test-dest-tag'
        expected = "No such tag: %s\n" % tag
        self.session.getTag.return_value = None
        with self.assertRaises(SystemExit) as ex:
            handle_add_target(self.options, self.session, [target, tag, dest_tag])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_add_target_tag_without_arch(self, stderr):
        tag_info = {'arches': None,
                    'extra': {},
                    'id': 1,
                    'locked': False,
                    'maven_include_all': False,
                    'maven_support': False,
                    'name': 'test-tag',
                    'perm': None,
                    'perm_id': None}
        target = 'test-target'
        tag = 'test-tag'
        dest_tag = 'test-dest-tag'
        expected = "Build tag has no arches: %s\n" % tag
        self.session.getTag.return_value = tag_info
        with self.assertRaises(SystemExit) as ex:
            handle_add_target(self.options, self.session, [target, tag, dest_tag])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_add_target_non_exist_dest_tag(self, stderr):
        side_effect_result = [{'arches': 'x86_64',
                               'extra': {},
                               'id': 1,
                               'locked': False,
                               'maven_include_all': False,
                               'maven_support': False,
                               'name': 'test-tag',
                               'perm': None,
                               'perm_id': None
                               },
                              None,
                              ]

        target = 'test-target'
        tag = 'test-tag'
        dest_tag = 'test-dest-tag'
        expected = "No such destination tag: %s\n" % dest_tag
        self.session.getTag.side_effect = side_effect_result
        with self.assertRaises(SystemExit) as ex:
            handle_add_target(self.options, self.session, [target, tag, dest_tag])
        self.assertExitCode(ex, 1)
        self.assert_console_message(stderr, expected)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_add_target_more_option(self, stderr):
        args = ['test-target', 'tag', 'test-dest-tag', 'tag-2']
        expected = "Usage: %s add-target <name> <build tag> <dest tag>\n" \
                   "(Specify the --help global option for a list of other help options)\n\n" \
                   "%s: error: Incorrect number of arguments\n" % (self.progname, self.progname)
        with self.assertRaises(SystemExit) as ex:
            handle_add_target(self.options, self.session, args)
        self.assertExitCode(ex, 2)
        self.assert_console_message(stderr, expected)

    def test_add_target_valid(self):
        side_effect_result = [{'arches': 'x86_64',
                               'extra': {},
                               'id': 1,
                               'locked': False,
                               'maven_include_all': False,
                               'maven_support': False,
                               'name': 'test-tag',
                               'perm': None,
                               'perm_id': None
                               },
                              {'arches': 'x86_64',
                               'extra': {},
                               'id': 2,
                               'locked': False,
                               'maven_include_all': False,
                               'maven_support': False,
                               'name': 'test-target',
                               'perm': None,
                               'perm_id': None
                               },
                              ]

        target = 'test-target'
        tag = 'test-tag'
        self.session.getTag.side_effect = side_effect_result
        self.session.createBuildTarget.return_value = None
        rv = handle_add_target(self.options, self.session, [target, tag])
        self.assertEqual(rv, None)
        self.session.createBuildTarget.assert_called_once_with(target, tag, target)
        self.session.getTag.assert_called_with(target)

    @mock.patch('sys.stderr', new_callable=StringIO)
    def test_add_target_without_perms(self, stderr):
        side_effect_result = [False, False]

        target = 'test-target'
        tag = 'test-tag'
        self.session.hasPerm.side_effect = side_effect_result
        with self.assertRaises(SystemExit) as ex:
            handle_add_target(self.options, self.session, [target, tag])
        self.assertExitCode(ex, 2)
        expected_msg = """Usage: %s add-target <name> <build tag> <dest tag>
(Specify the --help global option for a list of other help options)

%s: error: This action requires target or admin privileges
""" % (self.progname, self.progname)
        self.assert_console_message(stderr, expected_msg)
        self.session.createBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()

    def test_add_target_help(self):
        self.assert_help(
            handle_add_target,
            """Usage: %s add-target <name> <build tag> <dest tag>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)
