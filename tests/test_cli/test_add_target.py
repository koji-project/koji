from __future__ import absolute_import

try:
    from unittest import mock
except ImportError:
    import mock

import koji
from koji_cli.commands import handle_add_target
from . import utils


class TestAddTarget(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s add-target <name> <build tag> <dest tag>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)

    def tearDown(self):
        mock.patch.stopall()

    def test_add_target_without_option(self,):
        expected = self.format_error_message(
            "Please specify a target name, a build tag, and destination tag")
        self.assert_system_exit(
            handle_add_target,
            self.options, self.session, [],
            stdout='',
            stderr=expected,
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()

    def test_add_target_non_exist_tag(self):
        target = 'test-target'
        tag = 'test-tag'
        dest_tag = 'test-dest-tag'
        arguments = [target, tag, dest_tag]
        self.session.getTag.return_value = None
        self.assert_system_exit(
            handle_add_target,
            self.options, self.session, arguments,
            stdout='',
            stderr="No such tag: %s\n" % tag,
            exit_code=1,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_add_target_tag_without_arch(self,):
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
        self.session.getTag.return_value = tag_info
        arguments = [target, tag, dest_tag]
        self.assert_system_exit(
            handle_add_target,
            self.options, self.session, arguments,
            stdout='',
            stderr="Build tag has no arches: %s\n" % tag,
            exit_code=1,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_add_target_non_exist_dest_tag(self):
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
        self.session.getTag.side_effect = side_effect_result
        arguments = [target, tag, dest_tag]
        self.assert_system_exit(
            handle_add_target,
            self.options, self.session, arguments,
            stdout='',
            stderr="No such destination tag: %s\n" % dest_tag,
            exit_code=1,
            activate_session=None)
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_add_target_more_option(self):
        arguments = ['test-target', 'tag', 'test-dest-tag', 'tag-2']
        self.assert_system_exit(
            handle_add_target,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("Incorrect number of arguments"),
            exit_code=2,
            activate_session=None)
        self.activate_session_mock.assert_not_called()

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
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_add_target_without_perms(self):
        side_effect_result = [False, False]

        target = 'test-target'
        tag = 'test-tag'
        self.session.hasPerm.side_effect = side_effect_result
        arguments = [target, tag]
        self.assert_system_exit(
            handle_add_target,
            self.options, self.session, arguments,
            stdout='',
            stderr=self.format_error_message("This action requires target or admin privileges"),
            exit_code=2,
            activate_session=None)
        self.session.createBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        self.activate_session_mock.assert_called_once_with(self.session, self.options)

    def test_add_target_help(self):
        self.assert_help(
            handle_add_target,
            """Usage: %s add-target <name> <build tag> <dest tag>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help  show this help message and exit
""" % self.progname)
