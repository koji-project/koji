from __future__ import absolute_import

import copy

try:
    from unittest import mock
except ImportError:
    import mock
from six.moves import StringIO

import koji
from koji_cli.commands import handle_edit_target
from . import utils


class TestEditTarget(utils.CliTestCase):
    def setUp(self):
        self.options = mock.MagicMock()
        self.options.debug = False
        self.session = mock.MagicMock()
        self.session.getAPIVersion.return_value = koji.API_VERSION
        self.activate_session_mock = mock.patch('koji_cli.commands.activate_session').start()
        self.error_format = """Usage: %s edit-target [options] <name>
(Specify the --help global option for a list of other help options)

%s: error: {message}
""" % (self.progname, self.progname)
        self.build_target_info = {'build_tag': 444,
                                  'build_tag_name': 'test-tag',
                                  'dest_tag': 445,
                                  'dest_tag_name': 'dest-test-tag',
                                  'id': 1,
                                  'name': 'test-target'}
        self.dest_tag_info = {'arches': 'x86_64',
                              'extra': {},
                              'id': 1,
                              'name': 'new-dest-tag'}
        self.build_tag_info = {'arches': 'x86_64',
                               'extra': {},
                               'id': 1,
                               'name': 'new-build-tag'}
        self.target = 'test-target'
        self.dest_tag = 'test-dest-tag'
        self.new_target_name = 'new-test-target'
        self.new_dest_tag = 'new-dest-tag'
        self.new_build_tag = 'new-build-tag'

    def tearDown(self):
        mock.patch.stopall()

    def test_edit_target_without_option(self):
        expected = self.format_error_message("Please specify a build target")
        self.assert_system_exit(
            handle_edit_target,
            self.options,
            self.session,
            [],
            stdout='',
            stderr=expected,
            activate_session=None,
            exit_code=2
        )
        self.activate_session_mock.assert_not_called()
        self.session.getBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.editBuildTarget.assert_not_called()

    def test_edit_target_non_exist_target(self):
        expected = "No such build target: %s" % self.target
        self.session.getBuildTarget.return_value = None
        with self.assertRaises(koji.GenericError) as cm:
            handle_edit_target(self.options, self.session, [self.target])
        self.assertEqual(expected, str(cm.exception))
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_not_called()
        self.session.editBuildTarget.assert_not_called()
        self.activate_session_mock.assert_called_with(self.session, self.options)

    def test_edit_target_non_exist_dest_tag(self):
        self.session.getTag.return_value = None
        self.assert_system_exit(
            handle_edit_target,
            self.options,
            self.session,
            ['--dest-tag', self.dest_tag, self.target],
            stdout='',
            stderr="No such destination tag: %s\n" % self.dest_tag,
            activate_session=None,
            exit_code=1
        )
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.getTag.assert_called_once_with(self.dest_tag)
        self.session.editBuildTarget.assert_not_called()
        self.activate_session_mock.assert_called_with(self.session, self.options)

    def test_edit_target_without_perms(self):
        side_effect_result = [False, False]
        self.session.hasPerm.side_effect = side_effect_result
        expected = self.format_error_message("This action requires target or admin privileges")
        self.assert_system_exit(
            handle_edit_target,
            self.options,
            self.session,
            [self.target],
            stdout='',
            stderr=expected,
            activate_session=None,
            exit_code=2
        )
        self.session.editBuildTarget.assert_not_called()
        self.session.getTag.assert_not_called()
        self.session.getBuildTarget.assert_not_called()
        self.activate_session_mock.assert_called_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_edit_target_new_name(self, stdout):
        self.session.getBuildTarget.return_value = self.build_target_info
        rv = handle_edit_target(self.options, self.session, ['--rename', self.new_target_name,
                                                             self.target])
        self.assertEqual(rv, None)
        expected_msg = ''
        self.assert_console_message(stdout, expected_msg)
        self.session.getTag.assert_not_called()
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.editBuildTarget.assert_called_once_with(
            self.build_target_info['orig_name'], self.new_target_name,
            self.build_target_info['build_tag_name'], self.build_target_info['dest_tag_name'])
        self.activate_session_mock.assert_called_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_edit_target_dest_tag(self, stdout):
        self.session.getBuildTarget.return_value = self.build_target_info
        self.session.getTag.return_value = self.dest_tag_info
        rv = handle_edit_target(self.options, self.session, ['--dest-tag', self.new_dest_tag,
                                                             self.target])
        self.assertEqual(rv, None)
        expected_msg = ''
        self.assert_console_message(stdout, expected_msg)
        self.session.getTag.assert_called_once_with(self.new_dest_tag)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.editBuildTarget.assert_called_once_with(
            self.build_target_info['orig_name'], self.build_target_info['name'],
            self.build_target_info['build_tag_name'], self.build_target_info['dest_tag_name'])
        self.activate_session_mock.assert_called_with(self.session, self.options)

    def test_edit_target_non_exist_build_tag(self):
        self.session.getBuildTarget.return_value = self.build_target_info
        self.session.getTag.return_value = None
        self.assert_system_exit(
            handle_edit_target,
            self.options,
            self.session,
            ['--build-tag', self.new_build_tag, self.target],
            stdout='',
            stderr="No such tag: %s\n" % self.new_build_tag,
            activate_session=None,
            exit_code=1
        )
        self.session.getTag.assert_called_once_with(self.new_build_tag)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.editBuildTarget.assert_not_called()
        self.activate_session_mock.assert_called_with(self.session, self.options)

    def test_edit_target_tag_arch_none(self):
        build_tag_info = copy.deepcopy(self.build_tag_info)
        build_tag_info['arches'] = ''
        self.session.getBuildTarget.return_value = self.build_target_info
        self.session.getTag.return_value = build_tag_info
        self.assert_system_exit(
            handle_edit_target,
            self.options,
            self.session,
            ['--build-tag', self.new_build_tag, self.target],
            stdout='',
            stderr="Build tag has no arches: %s\n" % self.new_build_tag,
            activate_session=None,
            exit_code=1
        )
        self.session.getTag.assert_called_once_with(self.new_build_tag)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.editBuildTarget.assert_not_called()
        self.activate_session_mock.assert_called_with(self.session, self.options)

    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_edit_target_build_tag_valid(self, stdout):
        self.session.getBuildTarget.return_value = self.build_target_info
        self.session.getTag.return_value = self.build_tag_info
        rv = handle_edit_target(self.options, self.session, ['--build-tag', self.new_build_tag,
                                                             self.target])
        self.assertEqual(rv, None)
        expected_msg = ''
        self.assert_console_message(stdout, expected_msg)
        self.session.getTag.assert_called_once_with(self.new_build_tag)
        self.session.getBuildTarget.assert_called_once_with(self.target)
        self.session.editBuildTarget.assert_called_once_with(
            self.build_target_info['orig_name'], self.build_target_info['name'],
            self.build_target_info['build_tag_name'], self.build_target_info['dest_tag_name'])
        self.activate_session_mock.assert_called_with(self.session, self.options)

    def test_edit_target_help(self):
        self.assert_help(
            handle_edit_target,
            """Usage: %s edit-target [options] <name>
(Specify the --help global option for a list of other help options)

Options:
  -h, --help            show this help message and exit
  --rename=RENAME       Specify new name for target
  --build-tag=BUILD_TAG
                        Specify a different build tag
  --dest-tag=DEST_TAG   Specify a different destination tag
""" % self.progname)
